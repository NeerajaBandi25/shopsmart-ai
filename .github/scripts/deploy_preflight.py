"""Fail-closed preflight for production deployments from the latest main commit."""

from __future__ import annotations

import json
import os
import re
import sys
import unittest
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
WORKFLOW_FILE = "test.yml"
WORKFLOW_PATH = ".github/workflows/test.yml"
REQUIRED_CHECKS = (
    "Backend tests (pytest, PostgreSQL)",
    "Backend security gates (Ruff, pip-audit)",
    "Frontend tests (jest, lint, prettier)",
    "Docker Compose smoke test",
)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class PreflightError(ValueError):
    """Raised when the production deployment preconditions are not met."""


def api_get_json(path: str, *, token: str, api_root: str = API_ROOT) -> dict[str, Any]:
    request = Request(
        f"{api_root}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "shopsmart-production-preflight",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw_data = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        raise PreflightError(f"GitHub API request failed with HTTP {error.code}") from None
    except (URLError, TimeoutError, OSError):
        raise PreflightError("GitHub API request failed; retry the deployment preflight") from None

    if len(raw_data) > MAX_RESPONSE_BYTES:
        raise PreflightError("GitHub API response exceeded the configured size limit")
    try:
        payload = json.loads(raw_data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PreflightError("GitHub API returned an invalid JSON response") from None
    if not isinstance(payload, dict):
        raise PreflightError("GitHub API returned an unexpected response")
    return payload


def validate_repository(repository: str) -> None:
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise PreflightError("GITHUB_REPOSITORY must be in owner/repository format")


def validate_dispatch_target(ref: str, sha: str, current_main_sha: str) -> None:
    if ref != "refs/heads/main":
        raise PreflightError("Production deployments can only be dispatched from refs/heads/main")
    if not SHA_PATTERN.fullmatch(sha) or not SHA_PATTERN.fullmatch(current_main_sha):
        raise PreflightError("The dispatch or current main reference is not a valid commit SHA")
    if sha != current_main_sha:
        raise PreflightError("The dispatched commit is no longer the current main commit")


def select_latest_push_run(runs: list[dict[str, Any]], sha: str) -> dict[str, Any]:
    candidates = [
        run
        for run in runs
        if isinstance(run, dict)
        and run.get("head_sha") == sha
        and run.get("head_branch") == "main"
        and run.get("event") == "push"
        and run.get("path") == WORKFLOW_PATH
    ]
    if not candidates:
        raise PreflightError("No CI push run for .github/workflows/test.yml exists on this main commit")

    for run in candidates:
        if not isinstance(run.get("run_number"), int) or not isinstance(run.get("id"), int):
            raise PreflightError("GitHub returned an invalid CI workflow run")
    return max(candidates, key=lambda run: (run["run_number"], run["id"]))


def validate_ci_run(run: dict[str, Any], jobs: list[dict[str, Any]], sha: str) -> int:
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise PreflightError("The latest CI push run for main is not successful")
    if run.get("head_sha") != sha or run.get("head_branch") != "main":
        raise PreflightError("The selected CI run does not match the current main commit")

    attempt = run.get("run_attempt")
    if not isinstance(attempt, int) or attempt < 1:
        raise PreflightError("GitHub returned an invalid CI run attempt")

    matching_jobs: dict[str, list[dict[str, Any]]] = {
        check_name: [] for check_name in REQUIRED_CHECKS
    }
    for job in jobs:
        if not isinstance(job, dict):
            continue
        name = job.get("name")
        if name in matching_jobs:
            matching_jobs[name].append(job)

    for check_name, check_jobs in matching_jobs.items():
        if len(check_jobs) != 1:
            raise PreflightError(f"Expected exactly one latest CI job named: {check_name}")
        job = check_jobs[0]
        if job.get("run_attempt") != attempt or job.get("head_sha") != sha:
            raise PreflightError(f"The latest attempt for CI job {check_name} is stale")
        if job.get("status") != "completed" or job.get("conclusion") != "success":
            raise PreflightError(f"The latest attempt for CI job {check_name} is not successful")

    return attempt


def run_preflight(
    *,
    repository: str,
    ref: str,
    sha: str,
    token: str,
    api_root: str = API_ROOT,
) -> tuple[int, int]:
    validate_repository(repository)
    if not token:
        raise PreflightError("GITHUB_TOKEN is required for the read-only deployment preflight")

    current_main = api_get_json(
        f"/repos/{repository}/commits/main", token=token, api_root=api_root
    ).get("sha")
    if not isinstance(current_main, str):
        raise PreflightError("GitHub did not return the current main commit SHA")
    validate_dispatch_target(ref, sha, current_main)

    query = urlencode(
        {
            "branch": "main",
            "event": "push",
            "head_sha": sha,
            "per_page": 100,
        }
    )
    run_payload = api_get_json(
        f"/repos/{repository}/actions/workflows/{WORKFLOW_FILE}/runs?{query}",
        token=token,
        api_root=api_root,
    )
    runs = run_payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise PreflightError("GitHub did not return the CI workflow runs")
    latest_run = select_latest_push_run(runs, sha)
    run_id = latest_run["id"]
    attempt = latest_run.get("run_attempt")
    if not isinstance(attempt, int) or attempt < 1:
        raise PreflightError("GitHub returned an invalid CI run attempt")

    jobs_payload = api_get_json(
        f"/repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100",
        token=token,
        api_root=api_root,
    )
    jobs = jobs_payload.get("jobs")
    if not isinstance(jobs, list):
        raise PreflightError("GitHub did not return the latest CI attempt jobs")
    validated_attempt = validate_ci_run(latest_run, jobs, sha)
    return run_id, validated_attempt


def main() -> int:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    ref = os.environ.get("GITHUB_REF", "")
    sha = os.environ.get("GITHUB_SHA", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    try:
        run_id, attempt = run_preflight(
            repository=repository,
            ref=ref,
            sha=sha,
            token=token,
        )
    except PreflightError as error:
        print(f"Deployment preflight failed: {error}", file=sys.stderr)
        return 1

    print(f"Deployment preflight passed: sha={sha}, ci_run={run_id}, attempt={attempt}")
    return 0


class PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sha = "a" * 40

    def test_dispatch_requires_main_and_current_sha(self) -> None:
        validate_dispatch_target("refs/heads/main", self.sha, self.sha)
        with self.assertRaisesRegex(PreflightError, "refs/heads/main"):
            validate_dispatch_target("refs/heads/feature", self.sha, self.sha)
        with self.assertRaisesRegex(PreflightError, "no longer"):
            validate_dispatch_target("refs/heads/main", self.sha, "b" * 40)

    def test_selects_latest_push_run_for_the_expected_workflow(self) -> None:
        older = self.valid_run(run_number=10, run_id=100)
        latest = self.valid_run(run_number=11, run_id=101)
        wrong_sha = self.valid_run(run_number=12, run_id=102, sha="b" * 40)
        manual = self.valid_run(run_number=13, run_id=103, event="workflow_dispatch")
        selected = select_latest_push_run([older, latest, wrong_sha, manual], self.sha)
        self.assertEqual(selected["id"], 101)

    def test_missing_ci_run_fails_closed(self) -> None:
        with self.assertRaisesRegex(PreflightError, "No CI push run"):
            select_latest_push_run([], self.sha)

    def test_run_preflight_queries_current_sha_and_latest_attempt(self) -> None:
        run = self.valid_run(run_number=11, run_id=101, run_attempt=2)
        with patch(f"{__name__}.api_get_json") as mocked_api:
            mocked_api.side_effect = [
                {"sha": self.sha},
                {"workflow_runs": [run]},
                {"jobs": self.valid_jobs(run_attempt=2)},
            ]
            result = run_preflight(
                repository="NeerajaBandi25/shopsmart-ai",
                ref="refs/heads/main",
                sha=self.sha,
                token="offline-test-token",
                api_root="https://api.github.invalid",
            )

        self.assertEqual(result, (101, 2))
        self.assertEqual(mocked_api.call_count, 3)
        self.assertIn("commits/main", mocked_api.call_args_list[0].args[0])
        self.assertIn(self.sha, mocked_api.call_args_list[1].args[0])
        self.assertIn("attempts/2/jobs", mocked_api.call_args_list[2].args[0])

    def test_all_required_jobs_must_succeed_on_latest_attempt(self) -> None:
        run = self.valid_run(run_attempt=2)
        jobs = self.valid_jobs(run_attempt=2)
        self.assertEqual(validate_ci_run(run, jobs, self.sha), 2)

        for status, conclusion in (
            ("in_progress", None),
            ("completed", "failure"),
            ("completed", "cancelled"),
            ("completed", "neutral"),
        ):
            with self.subTest(status=status, conclusion=conclusion):
                bad_jobs = self.valid_jobs(run_attempt=2)
                bad_jobs[0]["status"] = status
                bad_jobs[0]["conclusion"] = conclusion
                with self.assertRaisesRegex(PreflightError, "not successful"):
                    validate_ci_run(run, bad_jobs, self.sha)

    def test_missing_duplicate_or_stale_jobs_fail_closed(self) -> None:
        run = self.valid_run()
        missing = self.valid_jobs()[:-1]
        with self.assertRaisesRegex(PreflightError, "exactly one"):
            validate_ci_run(run, missing, self.sha)

        duplicate = self.valid_jobs()
        duplicate.append(dict(duplicate[0]))
        with self.assertRaisesRegex(PreflightError, "exactly one"):
            validate_ci_run(run, duplicate, self.sha)

        stale = self.valid_jobs()
        stale[0]["run_attempt"] = 1
        run["run_attempt"] = 2
        with self.assertRaisesRegex(PreflightError, "stale"):
            validate_ci_run(run, stale, self.sha)

    def test_failed_or_incomplete_workflow_run_fails_closed(self) -> None:
        run = self.valid_run()
        jobs = self.valid_jobs()
        run["status"] = "in_progress"
        with self.assertRaisesRegex(PreflightError, "run.*not successful"):
            validate_ci_run(run, jobs, self.sha)

        run["status"] = "completed"
        run["conclusion"] = "failure"
        with self.assertRaisesRegex(PreflightError, "run.*not successful"):
            validate_ci_run(run, jobs, self.sha)

    def valid_run(
        self,
        *,
        run_number: int = 1,
        run_id: int = 10,
        run_attempt: int = 1,
        sha: str | None = None,
        event: str = "push",
    ) -> dict[str, Any]:
        return {
            "id": run_id,
            "run_number": run_number,
            "run_attempt": run_attempt,
            "head_sha": sha or self.sha,
            "head_branch": "main",
            "path": WORKFLOW_PATH,
            "event": event,
            "status": "completed",
            "conclusion": "success",
        }

    def valid_jobs(self, *, run_attempt: int = 1) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "run_attempt": run_attempt,
                "head_sha": self.sha,
                "status": "completed",
                "conclusion": "success",
            }
            for name in REQUIRED_CHECKS
        ]


def self_test() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PreflightTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        raise SystemExit(self_test())
    raise SystemExit(main())
