"""One-shot, SHA-authorized Prettier repair controller for Phase 6B."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from unittest.mock import patch


API_ROOT = "https://api.github.com"
ALLOWLISTED_PATH = "frontend/src/app/page.tsx"
FAILURE_CLASS = "frontend-prettier-formatting-only"
CI_WORKFLOW_PATH = ".github/workflows/test.yml"
REQUIRED_JOBS = {
    "Backend tests (pytest, PostgreSQL)",
    "Backend security gates (Ruff, pip-audit)",
    "Frontend tests (jest, lint, prettier)",
    "Docker Compose smoke test",
}
AUTHORIZATION_PATTERN = re.compile(
    r"\APHASE6B REPAIR AUTHORIZATION\n"
    r"PR: ([1-9][0-9]*)\n"
    r"HEAD_SHA: ([0-9a-f]{40}|[0-9a-f]{64})\n"
    r"SOURCE_RUN: ([1-9][0-9]*)\n"
    r"FAILURE_CLASS: frontend-prettier-formatting-only\n"
    r"PATH: frontend/src/app/page\.tsx\n"
    r"ATTEMPTS: 1\Z"
)
TRUSTED_ASSOCIATIONS = frozenset({"OWNER"})


class Rejected(Exception):
    """An ineligible event; callers must stop without a branch write."""


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        return None


def parse_authorization(comment: dict[str, Any]) -> dict[str, str] | None:
    if comment.get("author_association") not in TRUSTED_ASSOCIATIONS:
        return None
    body = comment.get("body", "")
    normalized_body = body.replace("\r\n", "\n").replace("\r", "\n")
    match = AUTHORIZATION_PATTERN.fullmatch(normalized_body)
    if match is None:
        return None
    return {
        "pr_number": match.group(1),
        "head_sha": match.group(2),
        "source_run_id": match.group(3),
        "failure_class": FAILURE_CLASS,
        "path": ALLOWLISTED_PATH,
        "comment_id": str(comment.get("id", "")),
    }


def validate_source(
    run: dict[str, Any],
    jobs: list[dict[str, Any]],
    pr: dict[str, Any],
    changed_files: list[str],
    *,
    repository: str,
    pr_number: int,
) -> tuple[bool, str]:
    run_path = str(run.get("path", "")).split("@", maxsplit=1)[0]
    if run.get("name") != "CI" or run_path != CI_WORKFLOW_PATH:
        return False, "wrong-source-workflow"
    if type(run.get("workflow_id")) is not int or run["workflow_id"] <= 0:
        return False, "missing-source-workflow-id"
    if run.get("event") != "pull_request":
        return False, "wrong-source-event"
    if run.get("conclusion") != "failure":
        return False, "source-run-not-failed"
    if run.get("run_attempt") != 1:
        return False, "source-run-rerun"
    if run.get("repository", {}).get("full_name") != repository:
        return False, "wrong-repository"
    associated = run.get("pull_requests") or []
    if len(associated) != 1 or associated[0].get("number") != pr_number:
        return False, "missing-or-ambiguous-pr-association"
    if pr.get("number") != pr_number or pr.get("state") != "open":
        return False, "pull-request-closed-or-mismatched"
    if pr.get("draft") is not False:
        return False, "pull-request-draft-or-unknown"
    if pr.get("base", {}).get("ref") != "main":
        return False, "wrong-base-branch"
    head_repo = pr.get("head", {}).get("repo") or {}
    if head_repo.get("full_name") != repository:
        return False, "fork-or-cross-repository-pr"
    run_sha = run.get("head_sha")
    if not isinstance(run_sha, str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", run_sha):
        return False, "invalid-source-sha"
    if pr.get("head", {}).get("sha") != run_sha:
        return False, "stale-source-sha"
    if changed_files != [ALLOWLISTED_PATH]:
        return False, "changed-file-set-not-allowlisted"

    by_name = {job.get("name"): job for job in jobs}
    if set(by_name) != REQUIRED_JOBS:
        return False, "required-job-set-mismatch"
    failed_jobs = [job for job in jobs if job.get("conclusion") == "failure"]
    if len(failed_jobs) != 1 or failed_jobs[0].get("name") != "Frontend tests (jest, lint, prettier)":
        return False, "wrong-failure-class"
    frontend_job = failed_jobs[0]
    failed_steps = [step for step in frontend_job.get("steps", []) if step.get("conclusion") == "failure"]
    if len(failed_steps) != 1 or failed_steps[0].get("name") != "Check formatting (prettier)":
        return False, "wrong-failure-step"
    if any(
        job.get("name") != frontend_job.get("name") and job.get("conclusion") != "success"
        for job in jobs
    ):
        return False, "unrelated-check-failed-or-incomplete"
    return True, "eligible"


def validate_authorization(
    comments: list[dict[str, Any]],
    *,
    pr_number: int,
    head_sha: str,
    source_run_id: int,
    required_comment_id: str | None = None,
) -> dict[str, str] | None:
    for comment in comments:
        authorization = parse_authorization(comment)
        if authorization is None:
            continue
        if (
            authorization["pr_number"] == str(pr_number)
            and authorization["head_sha"] == head_sha
            and authorization["source_run_id"] == str(source_run_id)
            and re.fullmatch(r"[1-9][0-9]*", authorization["comment_id"])
            and (required_comment_id is None or authorization["comment_id"] == required_comment_id)
        ):
            return authorization
    return None


def prior_attempt_run_found(
    runs: list[dict[str, Any]],
    *,
    pr_number: int,
    authorization_comment_id: str,
    current_run_id: str,
) -> bool:
    expected_title = f"CI Failure Repair PR #{pr_number} authorization-comment={authorization_comment_id}"
    matching_runs = [
        run
        for run in runs
        if run.get("display_title") == expected_title
        and str(run.get("id", "")) != current_run_id
    ]
    run_ids = [run.get("id") for run in matching_runs]
    if any(type(run_id) is not int or run_id <= 0 for run_id in run_ids):
        raise Rejected("repair-workflow-history-ambiguous")
    if len(run_ids) != len(set(run_ids)) or len(matching_runs) > 1:
        raise Rejected("repair-workflow-history-ambiguous")
    return bool(matching_runs)


def verify_diff(paths: list[str]) -> bool:
    return paths == [ALLOWLISTED_PATH]


def tree_entries_by_path(tree_response: dict[str, Any]) -> dict[str, tuple[str, str, str]]:
    entries = tree_response.get("tree")
    if tree_response.get("truncated") is not False or not isinstance(entries, list):
        raise Rejected("git-tree-history-incomplete")
    result: dict[str, tuple[str, str, str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise Rejected("git-tree-entry-invalid")
        path = entry.get("path")
        mode = entry.get("mode")
        entry_type = entry.get("type")
        sha = entry.get("sha")
        if not isinstance(path, str) or not path or not isinstance(mode, str):
            raise Rejected("git-tree-entry-invalid")
        if entry_type == "tree":
            continue
        if entry_type not in {"blob", "commit"} or not isinstance(sha, str):
            raise Rejected("git-tree-entry-invalid")
        if path in result:
            raise Rejected("git-tree-entry-duplicated")
        result[path] = (mode, entry_type, sha)
    return result


def verify_one_file_tree_change(
    base_tree: dict[str, Any], repaired_tree: dict[str, Any]
) -> None:
    before = tree_entries_by_path(base_tree)
    after = tree_entries_by_path(repaired_tree)
    before_target = before.get(ALLOWLISTED_PATH)
    after_target = after.get(ALLOWLISTED_PATH)
    if (
        before_target is None
        or after_target is None
        or before_target[1] != "blob"
        or after_target[1] != "blob"
        or before_target[0] not in {"100644", "100755"}
        or after_target[0] != "100644"
    ):
        raise Rejected("allowlisted-target-deleted-renamed-or-not-a-regular-file")
    changed = sorted(
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    )
    if changed != [ALLOWLISTED_PATH]:
        raise Rejected("git-tree-changes-not-exactly-allowlisted-file")


def workflow_write_permission_jobs(workflow_text: str) -> dict[str, set[str]]:
    current_job: str | None = None
    writes: dict[str, set[str]] = {}
    for line in workflow_text.splitlines():
        job_match = re.fullmatch(r"  ([a-z][a-z0-9-]*):", line)
        if job_match:
            current_job = job_match.group(1)
            continue
        permission_match = re.fullmatch(r"      ([a-z][a-z-]*): write", line)
        if current_job is not None and permission_match:
            writes.setdefault(permission_match.group(1), set()).add(current_job)
    return writes


def run_formatter(formatter: str, config: str, target: str) -> None:
    target_path = Path(target)
    resolved = target_path.resolve(strict=True)
    if target_path.is_symlink() or not resolved.is_file() or resolved.stat().st_size > 1_000_000:
        raise Rejected("formatter-input-is-unsafe-or-too-large")
    if not target_path.as_posix().endswith(f"source/{ALLOWLISTED_PATH}"):
        raise Rejected("formatter-target-is-not-allowlisted")
    source_index = target_path.parts.index("source")
    suffix_length = len(target_path.parts) - source_index - 1
    if any(part.is_symlink() for part in target_path.parents[:suffix_length]):
        raise Rejected("formatter-target-path-contains-symlink")
    env = {key: value for key, value in os.environ.items() if key not in {"GH_TOKEN", "GITHUB_TOKEN"}}
    result = subprocess.run(
        ["node", formatter, "--write", "--config", config, "--no-editorconfig", target],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    if result.returncode:
        raise Rejected("pinned formatter failed")


def verify_formatted_content(formatter: str, config: str, target: str) -> str:
    target_path = Path(target)
    if not target_path.is_file() or target_path.is_symlink() or target_path.stat().st_size > 1_000_000:
        raise Rejected("formatter-artifact-is-unsafe-or-too-large")
    env = {key: value for key, value in os.environ.items() if key not in {"GH_TOKEN", "GITHUB_TOKEN"}}
    result = subprocess.run(
        ["node", formatter, "--config", config, "--no-editorconfig", target],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    if result.returncode:
        raise Rejected("pinned formatter validation failed")
    actual = target_path.read_text(encoding="utf-8")
    if result.stdout != actual:
        raise Rejected("artifact is not exactly the trusted formatter output")
    return hashlib.sha256(actual.encode("utf-8")).hexdigest()


def api_request(
    method: str,
    path: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    accept: str = "application/vnd.github+json",
) -> dict[str, Any] | list[Any]:
    if not path.startswith("/") or ".." in path or "?" in path and not path.startswith("/repos/"):
        raise Rejected("invalid GitHub API path")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        data=body,
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "shopsmart-phase6b-repair",
            **({"Content-Type": "application/json"} if payload is not None else {}),
        },
        method=method,
    )
    opener = urllib.request.build_opener(NoRedirectHandler())
    with opener.open(request, timeout=30) as response:
        raw = response.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise Rejected("GitHub API response exceeded size limit")
    return json.loads(raw.decode("utf-8")) if raw else {}


def paginated(path: str, *, token: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for page in range(1, 11):
        separator = "&" if "?" in path else "?"
        result = api_request("GET", f"{path}{separator}per_page=100&page={page}", token=token)
        if not isinstance(result, list):
            raise Rejected("unexpected paginated API response")
        values.extend(item for item in result if isinstance(item, dict))
        if len(result) < 100:
            return values
    raise Rejected("pagination limit exceeded")


def required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise Rejected(f"missing required input: {name}")
    return value


def repository_path(repository: str, suffix: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise Rejected("invalid repository identity")
    return f"/repos/{repository}/{suffix}"


def get_source_context(
    token: str, repository: str, source_run_id: int, pr_number: int
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[str]]:
    run = api_request("GET", repository_path(repository, f"actions/runs/{source_run_id}"), token=token)
    if not isinstance(run, dict) or type(run.get("workflow_id")) is not int:
        raise Rejected("invalid source run")
    workflow = api_request("GET", repository_path(repository, f"actions/workflows/{run['workflow_id']}"), token=token)
    if (
        not isinstance(workflow, dict)
        or workflow.get("name") != "CI"
        or workflow.get("path") != CI_WORKFLOW_PATH
        or workflow.get("state") != "active"
    ):
        raise Rejected("source-run-workflow-is-not-existing-ci")
    jobs_response = api_request(
        "GET", repository_path(repository, f"actions/runs/{source_run_id}/jobs?per_page=100"), token=token
    )
    if not isinstance(jobs_response, dict) or not isinstance(jobs_response.get("jobs"), list):
        raise Rejected("invalid source jobs response")
    pr = api_request("GET", repository_path(repository, f"pulls/{pr_number}"), token=token)
    if not isinstance(pr, dict):
        raise Rejected("invalid pull request")
    files = paginated(repository_path(repository, f"pulls/{pr_number}/files"), token=token)
    return run, pr, jobs_response["jobs"], [item.get("filename") for item in files]


def read_comments(token: str, repository: str, pr_number: int) -> list[dict[str, Any]]:
    return paginated(repository_path(repository, f"issues/{pr_number}/comments"), token=token)


def get_authorized_context(
    *,
    token: str,
    repository: str,
    source_run_id: int,
    pr_number: int,
    authorization_comment_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str], list[dict[str, Any]]]:
    run, pr, jobs, changed_paths = get_source_context(token, repository, source_run_id, pr_number)
    valid, reason = validate_source(run, jobs, pr, changed_paths, repository=repository, pr_number=pr_number)
    if not valid:
        raise Rejected(reason)
    comments = read_comments(token, repository, pr_number)
    authorization = validate_authorization(
        comments,
        pr_number=pr_number,
        head_sha=run["head_sha"],
        source_run_id=source_run_id,
        required_comment_id=authorization_comment_id,
    )
    if authorization is None:
        raise Rejected("missing-or-invalid-sha-bound-maintainer-authorization")
    return run, pr, authorization, comments


def validate_issue_authorization(token: str, repository: str) -> None:
    issue = api_request("GET", repository_path(repository, "issues/19"), token=token)
    if not isinstance(issue, dict) or issue.get("state") != "open":
        raise Rejected("pilot-issue-not-open")
    comments = read_comments(token, repository, 19)
    required_text = (
        "AUTHORIZATION — PHASE 6B SINGLE-REPAIR PILOT",
        "Failure class: Frontend Prettier formatting-only failure",
        "Allowed file: frontend/src/app/page.tsx",
        "Exactly ONE repair attempt",
    )
    if not any(
        comment.get("author_association") == "OWNER"
        and all(text in comment.get("body", "") for text in required_text)
        for comment in comments
    ):
        raise Rejected("issue-19-owner-authorization-missing")


def prior_attempt_consumed(
    token: str, repository: str, pr_number: int, authorization_comment_id: str
) -> bool:
    workflow_response = api_request("GET", repository_path(repository, "actions/workflows?per_page=100"), token=token)
    workflows = workflow_response.get("workflows", []) if isinstance(workflow_response, dict) else []
    repair_workflows = [
        item
        for item in workflows
        if item.get("path") == ".github/workflows/ci-failure-repair.yml" and item.get("state") == "active"
    ]
    if len(repair_workflows) != 1 or type(repair_workflows[0].get("id")) is not int:
        raise Rejected("repair-workflow-history-unavailable")
    workflow_id = repair_workflows[0]["id"]
    runs = paginated(
        repository_path(repository, f"actions/workflows/{workflow_id}/runs?event=issue_comment"), token=token
    )
    current_run_id = required_env("GITHUB_RUN_ID")
    expected_title = f"CI Failure Repair PR #{pr_number} authorization-comment={authorization_comment_id}"
    matched_runs = [
        run
        for run in runs
        if run.get("display_title") == expected_title
        and str(run.get("id", "")) != current_run_id
    ]
    return prior_attempt_run_found(
        matched_runs,
        pr_number=pr_number,
        authorization_comment_id=authorization_comment_id,
        current_run_id=current_run_id,
    )


def write_output(values: dict[str, str]) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    with open(output_file, "a", encoding="utf-8") as stream:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise Rejected("multiline workflow output rejected")
            stream.write(f"{key}={value}\n")


def preflight() -> None:
    token = required_env("GH_TOKEN")
    repository = required_env("REPOSITORY")
    event = json.loads(Path(required_env("GITHUB_EVENT_PATH")).read_text(encoding="utf-8"))
    issue = event.get("issue")
    comment = event.get("comment")
    if not isinstance(issue, dict) or not isinstance(issue.get("pull_request"), dict):
        raise Rejected("authorization-comment-is-not-on-a-pull-request")
    if not isinstance(comment, dict) or type(comment.get("id")) is not int or comment["id"] <= 0:
        raise Rejected("missing-triggering-authorization-comment")
    pr_number = issue.get("number")
    if type(pr_number) is not int or pr_number <= 0:
        raise Rejected("invalid-triggering-pull-request-number")
    comment_id = str(comment["id"])
    event_authorization = parse_authorization(comment)
    if event_authorization is None or event_authorization["pr_number"] != str(pr_number):
        raise Rejected("triggering-comment-is-not-valid-owner-authorization")
    source_run_id = int(event_authorization["source_run_id"])
    head_sha = event_authorization["head_sha"]
    if required_env("GITHUB_RUN_ATTEMPT") != "1":
        raise Rejected("repair-workflow-rerun-not-allowed")
    validate_issue_authorization(token, repository)
    run, pr, authorization, comments = get_authorized_context(
        token=token,
        repository=repository,
        source_run_id=source_run_id,
        pr_number=pr_number,
        authorization_comment_id=comment_id,
    )
    if authorization["head_sha"] != head_sha:
        raise Rejected("triggering-authorization-changed")
    if prior_attempt_consumed(token, repository, pr_number, comment_id):
        raise Rejected("authorization-attempt-already-consumed")
    latest_run, latest_pr, latest_authorization, latest_comments = get_authorized_context(
        token=token,
        repository=repository,
        source_run_id=source_run_id,
        pr_number=pr_number,
        authorization_comment_id=comment_id,
    )
    if (
        latest_run.get("head_sha") != head_sha
        or latest_pr.get("head", {}).get("sha") != head_sha
        or latest_pr.get("head", {}).get("ref") != pr.get("head", {}).get("ref")
        or latest_authorization["comment_id"] != comment_id
        or prior_attempt_consumed(token, repository, pr_number, comment_id)
    ):
        raise Rejected("PR-or-authorization-changed-before-attempt-consumption")
    write_output(
        {
            "eligible": "true",
            "pr_number": str(pr_number),
            "head_sha": head_sha,
            "head_ref": str(pr.get("head", {}).get("ref", "")),
            "authorization_comment_id": comment_id,
            "workflow_id": str(run.get("workflow_id", "")),
            "source_run_id": str(source_run_id),
        }
    )


def verify_source_command(args: argparse.Namespace) -> None:
    token = required_env("GH_TOKEN")
    repository = required_env("REPOSITORY")
    pr_number = int(required_env("PR_NUMBER"))
    expected_sha = required_env("EXPECTED_SHA")
    source_run_id = int(required_env("SOURCE_RUN_ID"))
    authorization_comment_id = required_env("AUTHORIZATION_COMMENT_ID")
    expected_head_ref = required_env("EXPECTED_HEAD_REF")
    run, pr, authorization, comments = get_authorized_context(
        token=token,
        repository=repository,
        source_run_id=source_run_id,
        pr_number=pr_number,
        authorization_comment_id=authorization_comment_id,
    )
    if (
        run.get("head_sha") != expected_sha
        or pr.get("head", {}).get("sha") != expected_sha
        or pr.get("head", {}).get("ref") != expected_head_ref
        or authorization["head_sha"] != expected_sha
        or authorization["comment_id"] != authorization_comment_id
    ):
        raise Rejected("authorization-or-head-changed-before-format")


def verify_working_tree() -> None:
    repo_dir = Path(required_env("REPO_DIR"))
    target = (repo_dir / ALLOWLISTED_PATH).resolve()
    if not target.is_file() or repo_dir.resolve() not in target.parents:
        raise Rejected("allowlisted-source-file-missing-or-unsafe")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    expected_status = f" M {ALLOWLISTED_PATH}"
    if status != [expected_status]:
        raise Rejected("working-tree-diff-is-not-one-allowlisted-file")
    names = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    if not verify_diff(names):
        raise Rejected("diff-path-is-not-allowlisted")
    subprocess.run(["git", "diff", "--check"], cwd=repo_dir, check=True, capture_output=True)
    original = subprocess.run(
        ["git", "show", f"HEAD:{ALLOWLISTED_PATH}"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    ).stdout
    if original == target.read_bytes():
        raise Rejected("formatter-produced-no-change")


def publish() -> None:
    token = required_env("GH_TOKEN")
    repository = required_env("REPOSITORY")
    pr_number = int(required_env("PR_NUMBER"))
    expected_sha = required_env("EXPECTED_SHA")
    source_run_id = int(required_env("SOURCE_RUN_ID"))
    authorization_comment_id = required_env("AUTHORIZATION_COMMENT_ID")
    expected_head_ref = required_env("EXPECTED_HEAD_REF")
    artifact_file = Path(required_env("ARTIFACT_FILE"))
    expected_artifact_hash = required_env("ARTIFACT_SHA256")

    run, pr, authorization, _comments = get_authorized_context(
        token=token,
        repository=repository,
        source_run_id=source_run_id,
        pr_number=pr_number,
        authorization_comment_id=authorization_comment_id,
    )
    if (
        run.get("head_sha") != expected_sha
        or pr.get("head", {}).get("sha") != expected_sha
        or pr.get("head", {}).get("ref") != expected_head_ref
        or authorization["head_sha"] != expected_sha
        or authorization["comment_id"] != authorization_comment_id
    ):
        raise Rejected("authorization-or-head-changed-before-publish")
    if pr.get("base", {}).get("ref") != "main":
        raise Rejected("base-branch-changed-before-publish")
    head_ref = pr.get("head", {}).get("ref")
    if not isinstance(head_ref, str) or not head_ref or head_ref == "main" or head_ref.startswith("-"):
        raise Rejected("invalid-head-branch")
    if not artifact_file.is_file() or artifact_file.is_symlink():
        raise Rejected("missing-or-unsafe-repair-artifact")
    content = artifact_file.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_artifact_hash:
        raise Rejected("repair-artifact-changed-after-validation")

    commit_data = api_request(
        "GET", repository_path(repository, f"git/commits/{expected_sha}"), token=token
    )
    base_tree = commit_data.get("tree", {}).get("sha")
    if not isinstance(base_tree, str):
        raise Rejected("could-not-read-base-commit-tree")
    base_tree_data = api_request("GET", repository_path(repository, f"git/trees/{base_tree}?recursive=1"), token=token)
    if not isinstance(base_tree_data, dict):
        raise Rejected("could-not-read-complete-base-tree")
    base_entries = tree_entries_by_path(base_tree_data)
    if ALLOWLISTED_PATH not in base_entries or base_entries[ALLOWLISTED_PATH][1] != "blob":
        raise Rejected("allowlisted-target-deleted-renamed-or-not-a-regular-file")
    blob = api_request(
        "POST",
        repository_path(repository, "git/blobs"),
        token=token,
        payload={"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"},
    )
    blob_sha = blob.get("sha")
    if not isinstance(blob_sha, str):
        raise Rejected("could-not-create-repair-blob")
    tree = api_request(
        "POST",
        repository_path(repository, "git/trees"),
        token=token,
        payload={
            "base_tree": base_tree,
            "tree": [{"path": ALLOWLISTED_PATH, "mode": "100644", "type": "blob", "sha": blob_sha}],
        },
    )
    tree_sha = tree.get("sha")
    if not isinstance(tree_sha, str):
        raise Rejected("could-not-create-repair-tree")
    repaired_tree_data = api_request(
        "GET", repository_path(repository, f"git/trees/{tree_sha}?recursive=1"), token=token
    )
    if not isinstance(repaired_tree_data, dict):
        raise Rejected("could-not-read-complete-repaired-tree")
    verify_one_file_tree_change(base_tree_data, repaired_tree_data)
    commit = api_request(
        "POST",
        repository_path(repository, "git/commits"),
        token=token,
        payload={
            "message": "style: format authorized frontend page",
            "tree": tree_sha,
            "parents": [expected_sha],
        },
    )
    repair_sha = commit.get("sha")
    if not isinstance(repair_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", repair_sha):
        raise Rejected("could-not-create-repair-commit")

    latest_run, latest_pr, latest_authorization, _latest_comments = get_authorized_context(
        token=token,
        repository=repository,
        source_run_id=source_run_id,
        pr_number=pr_number,
        authorization_comment_id=authorization_comment_id,
    )
    if (
        latest_run.get("head_sha") != expected_sha
        or latest_pr.get("number") != pr_number
        or latest_pr.get("head", {}).get("sha") != expected_sha
        or latest_pr.get("head", {}).get("ref") != expected_head_ref
        or latest_authorization["comment_id"] != authorization_comment_id
        or latest_authorization["failure_class"] != FAILURE_CLASS
        or latest_authorization["path"] != ALLOWLISTED_PATH
    ):
        raise Rejected("PR-or-authorization-changed-immediately-before-branch-write")

    encoded_ref = urllib.parse.quote(head_ref, safe="/")
    api_request(
        "PATCH",
        repository_path(repository, f"git/refs/heads/{encoded_ref}"),
        token=token,
        payload={"sha": repair_sha, "force": False},
    )
    write_output({"repair_sha": repair_sha})


def dispatch_ci() -> None:
    token = required_env("GH_TOKEN")
    repository = required_env("REPOSITORY")
    pr_number = int(required_env("PR_NUMBER"))
    expected_sha = required_env("EXPECTED_REPAIR_SHA")
    pr = api_request("GET", repository_path(repository, f"pulls/{pr_number}"), token=token)
    if (
        pr.get("state") != "open"
        or pr.get("draft") is not False
        or pr.get("base", {}).get("ref") != "main"
        or (pr.get("head", {}).get("repo") or {}).get("full_name") != repository
        or pr.get("head", {}).get("sha") != expected_sha
    ):
        raise Rejected("PR-head-changed-before-fresh-CI-dispatch")
    head_ref = pr.get("head", {}).get("ref")
    if not isinstance(head_ref, str) or not head_ref or head_ref == "main" or head_ref.startswith("-"):
        raise Rejected("invalid-PR-head-ref-for-dispatch")

    workflow_id = required_env("CI_WORKFLOW_ID")
    if not re.fullmatch(r"[1-9][0-9]*", workflow_id):
        raise Rejected("invalid-CI-workflow-id")
    runs_path = repository_path(repository, f"actions/workflows/{workflow_id}/runs")
    before = paginated(f"{runs_path}?event=workflow_dispatch&branch={urllib.parse.quote(head_ref, safe='')}", token=token)
    known_ids = {str(run.get("id")) for run in before}
    api_request(
        "POST",
        repository_path(repository, f"actions/workflows/{workflow_id}/dispatches"),
        token=token,
        payload={"ref": head_ref},
    )

    matching: dict[str, Any] | None = None
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        runs = paginated(
            f"{runs_path}?event=workflow_dispatch&branch={urllib.parse.quote(head_ref, safe='')}", token=token
        )
        matching = next(
            (
                run_value
                for run_value in runs
                if str(run_value.get("id")) not in known_ids
                and run_value.get("head_sha") == expected_sha
                and run_value.get("event") == "workflow_dispatch"
            ),
            None,
        )
        if matching:
            break
        time.sleep(5)
    if matching is None:
        raise Rejected("fresh-CI-dispatch-not-observed-on-repair-SHA")

    run_id = int(matching["id"])
    deadline = time.monotonic() + 3600
    while time.monotonic() < deadline:
        run_value = api_request("GET", repository_path(repository, f"actions/runs/{run_id}"), token=token)
        if run_value.get("head_sha") != expected_sha:
            raise Rejected("fresh-CI-run-SHA-mismatch")
        if run_value.get("status") == "completed":
            break
        time.sleep(10)
    else:
        raise Rejected("fresh-CI-run-did-not-complete")

    jobs_response = api_request(
        "GET", repository_path(repository, f"actions/runs/{run_id}/jobs?per_page=100"), token=token
    )
    jobs = jobs_response.get("jobs", [])
    results = {job.get("name"): job.get("conclusion") for job in jobs}
    if set(results) != REQUIRED_JOBS or any(value != "success" for value in results.values()):
        raise Rejected("fresh-CI-required-checks-not-all-successful")
    write_output({"fresh_ci_run_id": str(run_id), "fresh_ci_sha": expected_sha, "fresh_ci_result": "success"})


def self_test() -> None:
    sha = "a" * 40
    repository = "owner/repo"
    workflow_path = Path(__file__).resolve().parents[1] / "workflows" / "ci-failure-repair.yml"
    write_jobs = workflow_write_permission_jobs(workflow_path.read_text(encoding="utf-8"))
    assert write_jobs.get("contents") == {"publish"}
    assert not write_jobs.get("issues")
    assert not write_jobs.get("pull-requests")
    run = {
        "event": "pull_request",
        "name": "CI",
        "path": CI_WORKFLOW_PATH,
        "workflow_id": 10,
        "conclusion": "failure",
        "run_attempt": 1,
        "repository": {"full_name": repository},
        "head_sha": sha,
        "pull_requests": [{"number": 7}],
    }
    pr = {
        "number": 7,
        "state": "open",
        "draft": False,
        "head": {"sha": sha, "ref": "fix/page-format", "repo": {"full_name": repository}},
        "base": {"ref": "main"},
    }
    jobs = [
        {"name": name, "conclusion": "success", "steps": []} for name in sorted(REQUIRED_JOBS)
    ]
    frontend = next(job for job in jobs if job["name"] == "Frontend tests (jest, lint, prettier)")
    frontend["conclusion"] = "failure"
    frontend["steps"] = [{"name": "Check formatting (prettier)", "conclusion": "failure"}]
    files = [ALLOWLISTED_PATH]

    accepted, reason = validate_source(run, jobs, pr, files, repository=repository, pr_number=7)
    assert accepted and reason == "eligible"
    rejected: list[tuple[str, dict[str, Any], list[dict[str, Any]], dict[str, Any], list[str], int]] = []

    def reject(name: str, *, run_value: dict[str, Any] | None = None, jobs_value: list[dict[str, Any]] | None = None, pr_value: dict[str, Any] | None = None, paths: list[str] | None = None, number: int = 7) -> None:
        rejected.append((name, run_value or run, jobs_value or jobs, pr_value or pr, files if paths is None else paths, number))

    reject("wrong failure class", jobs_value=[{**j, "conclusion": "failure"} if j["name"] == "Backend tests (pytest, PostgreSQL)" else j for j in jobs])
    reject("wrong source workflow", run_value={**run, "path": ".github/workflows/other.yml"})
    reject("wrong failed step", jobs_value=[{**j, "steps": [{"name": "Build (next build)", "conclusion": "failure"}]} if j["name"] == "Frontend tests (jest, lint, prettier)" else j for j in jobs])
    reject("wrong file", paths=["frontend/src/app/other.tsx"])
    reject("multi-file diff", paths=[ALLOWLISTED_PATH, "README.md"])
    reject("stale SHA", pr_value={**pr, "head": {**pr["head"], "sha": "b" * 40}})
    reject("fork PR", pr_value={**pr, "head": {**pr["head"], "repo": {"full_name": "fork/repo"}}})
    reject("draft PR", pr_value={**pr, "draft": True})
    reject("closed PR", pr_value={**pr, "state": "closed"})
    reject("wrong PR number", number=8)
    reject("unrelated failing job", jobs_value=[{**j, "conclusion": "failure"} if j["name"] == "Backend security gates (Ruff, pip-audit)" else j for j in jobs])
    reject("rerun", run_value={**run, "run_attempt": 2})
    for name, run_value, jobs_value, pr_value, paths_value, number in rejected:
        allowed, why = validate_source(run_value, jobs_value, pr_value, paths_value, repository=repository, pr_number=number)
        assert not allowed, f"{name} unexpectedly eligible"
        assert why, f"{name} lacks a rejection reason"

    valid_comment = {
        "id": 99,
        "author_association": "OWNER",
        "body": (
            "PHASE6B REPAIR AUTHORIZATION\nPR: 7\nHEAD_SHA: "
            f"{sha}\nSOURCE_RUN: 123\nFAILURE_CLASS: {FAILURE_CLASS}\n"
            f"PATH: {ALLOWLISTED_PATH}\nATTEMPTS: 1"
        ),
    }
    parsed_lf = parse_authorization(valid_comment)
    assert parsed_lf is not None
    assert parse_authorization(
        {**valid_comment, "body": valid_comment["body"].replace("\n", "\r\n")}
    ) == parsed_lf
    assert parse_authorization(
        {**valid_comment, "body": valid_comment["body"].replace("\n", "\r")}
    ) == parsed_lf
    assert parse_authorization({**valid_comment, "author_association": "CONTRIBUTOR"}) is None

    invalid_authorization_bodies = [
        valid_comment["body"].replace("PHASE6B REPAIR AUTHORIZATION", "PHASE6B REPAIR"),
        valid_comment["body"].replace(f"HEAD_SHA: {sha}", f"HEAD_SHA: {sha[:7]}"),
        valid_comment["body"].replace(FAILURE_CLASS, "Frontend Prettier formatting-only failure"),
        valid_comment["body"].replace(ALLOWLISTED_PATH, "frontend/src/app/other.tsx"),
        valid_comment["body"].replace("ATTEMPTS: 1", "ATTEMPTS: 2"),
        valid_comment["body"] + "\nextra",
    ]
    for invalid_body in invalid_authorization_bodies:
        assert parse_authorization({**valid_comment, "body": invalid_body}) is None
    assert validate_authorization([valid_comment], pr_number=7, head_sha=sha, source_run_id=123)
    assert validate_authorization([valid_comment], pr_number=8, head_sha=sha, source_run_id=123) is None
    assert validate_authorization(
        [valid_comment], pr_number=7, head_sha=sha, source_run_id=123, required_comment_id="99"
    )
    assert validate_authorization(
        [valid_comment], pr_number=7, head_sha=sha, source_run_id=123, required_comment_id="100"
    ) is None
    assert validate_authorization([], pr_number=7, head_sha=sha, source_run_id=123) is None
    assert validate_authorization([valid_comment], pr_number=7, head_sha="b" * 40, source_run_id=123) is None
    assert validate_authorization([valid_comment], pr_number=7, head_sha=sha, source_run_id=124) is None
    assert validate_authorization([{**valid_comment, "author_association": "CONTRIBUTOR"}], pr_number=7, head_sha=sha, source_run_id=123) is None
    assert validate_authorization([{**valid_comment, "body": valid_comment["body"] + "\nextra"}], pr_number=7, head_sha=sha, source_run_id=123) is None
    prior_runs = [
        {"id": 455, "display_title": "CI Failure Repair PR #7 authorization-comment=99"},
        {"id": 457, "display_title": "CI Failure Repair PR #7 authorization-comment=101"},
        {"id": 456, "display_title": "CI Failure Repair PR #8 authorization-comment=100"},
    ]
    assert prior_attempt_run_found(
        prior_runs,
        pr_number=7,
        authorization_comment_id="99",
        current_run_id="999",
    )
    assert not prior_attempt_run_found(
        prior_runs,
        pr_number=7,
        authorization_comment_id="102",
        current_run_id="999",
    )
    try:
        prior_attempt_run_found(
            [prior_runs[0], {**prior_runs[0], "id": 458}],
            pr_number=7,
            authorization_comment_id="99",
            current_run_id="999",
        )
    except Rejected as error:
        assert str(error) == "repair-workflow-history-ambiguous"
    else:
        raise AssertionError("duplicate exact authorization history was accepted")
    try:
        prior_attempt_run_found(
            [{**prior_runs[0], "id": "invalid"}],
            pr_number=7,
            authorization_comment_id="99",
            current_run_id="999",
        )
    except Rejected as error:
        assert str(error) == "repair-workflow-history-ambiguous"
    else:
        raise AssertionError("malformed exact authorization history was accepted")

    history_api_calls: list[tuple[str, str]] = []

    def history_api(method: str, endpoint: str, **_: Any) -> dict[str, Any]:
        history_api_calls.append((method, endpoint))
        if endpoint.endswith("actions/workflows?per_page=100"):
            return {
                "workflows": [
                    {
                        "id": 20,
                        "path": ".github/workflows/ci-failure-repair.yml",
                        "state": "active",
                    }
                ]
            }
        raise AssertionError(endpoint)

    history_paths: list[str] = []

    def history_page(path: str, *, token: str) -> list[dict[str, Any]]:
        history_paths.append(path)
        return [prior_runs[0]]

    with patch.dict(os.environ, {"GITHUB_RUN_ID": "999"}, clear=False), patch(
        __name__ + ".api_request", side_effect=history_api
    ), patch(__name__ + ".paginated", side_effect=history_page):
        assert prior_attempt_consumed("mock-token", repository, 7, "99")
    assert all(method == "GET" for method, _ in history_api_calls)
    assert len(history_paths) == 1 and "runs?event=issue_comment" in history_paths[0]
    assert not any("/jobs" in endpoint for _, endpoint in history_api_calls)

    with patch(__name__ + ".api_request", return_value={"workflows": []}):
        try:
            prior_attempt_consumed("mock-token", repository, 7, "99")
        except Rejected as error:
            assert str(error) == "repair-workflow-history-unavailable"
        else:
            raise AssertionError("missing workflow history was accepted")
    assert verify_diff([ALLOWLISTED_PATH])
    assert not verify_diff([ALLOWLISTED_PATH, "README.md"])

    base_tree_fixture = {
        "truncated": False,
        "tree": [
            {"path": ALLOWLISTED_PATH, "mode": "100644", "type": "blob", "sha": "1" * 40},
            {"path": "README.md", "mode": "100644", "type": "blob", "sha": "2" * 40},
        ],
    }
    repaired_tree_fixture = {
        "truncated": False,
        "tree": [
            {"path": ALLOWLISTED_PATH, "mode": "100644", "type": "blob", "sha": "3" * 40},
            {"path": "README.md", "mode": "100644", "type": "blob", "sha": "2" * 40},
        ],
    }
    verify_one_file_tree_change(base_tree_fixture, repaired_tree_fixture)
    invalid_trees = [
        {
            "truncated": False,
            "tree": [
                *repaired_tree_fixture["tree"],
                {"path": "another.txt", "mode": "100644", "type": "blob", "sha": "4" * 40},
            ],
        },
        {"truncated": False, "tree": [repaired_tree_fixture["tree"][1]]},
        {
            "truncated": False,
            "tree": [
                {"path": "frontend/src/app/renamed.tsx", "mode": "100644", "type": "blob", "sha": "3" * 40},
                repaired_tree_fixture["tree"][1],
            ],
        },
    ]
    for invalid_tree in invalid_trees:
        try:
            verify_one_file_tree_change(base_tree_fixture, invalid_tree)
        except Rejected:
            pass
        else:
            raise AssertionError("multi-file, deleted, or renamed tree change was accepted")

    preflight_env = {
        "GH_TOKEN": "mock-token",
        "REPOSITORY": repository,
        "GITHUB_RUN_ID": "456",
        "GITHUB_RUN_ATTEMPT": "1",
    }
    event_directory = tempfile.TemporaryDirectory()
    event_path = Path(event_directory.name) / "event.json"
    event_path.write_text(
        json.dumps(
            {
                "issue": {"number": 7, "pull_request": {"url": "https://api.github.com/repos/owner/repo/pulls/7"}},
                "comment": valid_comment,
            }
        ),
        encoding="utf-8",
    )
    preflight_env["GITHUB_EVENT_PATH"] = str(event_path)
    valid_event = json.loads(event_path.read_text(encoding="utf-8"))
    invalid_events = [
        {**valid_event, "comment": {**valid_comment, "author_association": "CONTRIBUTOR"}},
        {**valid_event, "comment": {**valid_comment, "body": valid_comment["body"] + "\nextra"}},
        {**valid_event, "issue": {"number": 7}},
    ]
    for invalid_event in invalid_events:
        event_path.write_text(json.dumps(invalid_event), encoding="utf-8")
        with patch.dict(os.environ, preflight_env, clear=False):
            with patch(__name__ + ".api_request") as api_mock:
                try:
                    preflight()
                except Rejected:
                    pass
                else:
                    raise AssertionError("invalid triggering authorization was accepted")
                api_mock.assert_not_called()
    event_path.write_text(json.dumps(valid_event), encoding="utf-8")
    for name, run_value, jobs_value, pr_value, paths_value, number in rejected:
        env_value = preflight_env

        def checked_context(**_: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, str], list[dict[str, Any]]]:
            valid, failure_reason = validate_source(
                run_value, jobs_value, pr_value, paths_value, repository=repository, pr_number=number
            )
            if not valid:
                raise Rejected(failure_reason)
            raise Rejected("missing-or-invalid-sha-bound-maintainer-authorization")

        with patch.dict(os.environ, env_value, clear=False):
            with patch(__name__ + ".validate_issue_authorization"), patch(
                __name__ + ".prior_attempt_consumed", return_value=False
            ), patch(
                __name__ + ".get_authorized_context", side_effect=checked_context
            ), patch(__name__ + ".api_request") as api_mock:
                try:
                    preflight()
                except Rejected:
                    pass
                else:
                    raise AssertionError(f"{name} was not rejected by preflight")
                assert not any(call.args[0] in {"POST", "PATCH", "PUT", "DELETE"} for call in api_mock.call_args_list), (
                    f"{name} caused a write API request"
                )

    valid_authorization = {
        **validate_authorization([valid_comment], pr_number=7, head_sha=sha, source_run_id=123),
    }
    unused_comments: list[dict[str, Any]] = []
    with patch.dict(os.environ, preflight_env, clear=False):
        with patch(__name__ + ".validate_issue_authorization"), patch(
            __name__ + ".prior_attempt_consumed", return_value=False
        ), patch(__name__ + ".api_request", return_value={}) as api_mock, patch(
            __name__ + ".write_output"
        ) as output_mock, patch(
            __name__ + ".get_authorized_context",
            return_value=(run, pr, valid_authorization, unused_comments),
        ) as context_mock:
            preflight()
            assert context_mock.call_count == 2
            assert all(call.kwargs["authorization_comment_id"] == "99" for call in context_mock.call_args_list)
            assert not any(call.args[0] in {"POST", "PATCH", "PUT", "DELETE"} for call in api_mock.call_args_list)
            output_mock.assert_called_once()

    with patch.dict(os.environ, preflight_env, clear=False):
        with patch(__name__ + ".validate_issue_authorization"), patch(
            __name__ + ".prior_attempt_consumed", return_value=True
        ), patch(
            __name__ + ".get_authorized_context",
            return_value=(run, pr, valid_authorization, unused_comments),
        ), patch(__name__ + ".api_request") as api_mock:
            try:
                preflight()
            except Rejected as error:
                assert str(error) == "authorization-attempt-already-consumed"
            else:
                raise AssertionError("consumed PR authorization was accepted")
            api_mock.assert_not_called()

    for history_error in (True, Rejected("repair-workflow-history-unavailable")):
        history_patch = (
            patch(__name__ + ".prior_attempt_consumed", return_value=True)
            if history_error is True
            else patch(__name__ + ".prior_attempt_consumed", side_effect=history_error)
        )
        with patch.dict(os.environ, preflight_env, clear=False):
            with patch(__name__ + ".validate_issue_authorization"), history_patch, patch(
                __name__ + ".get_authorized_context",
                return_value=(run, pr, valid_authorization, unused_comments),
            ), patch(__name__ + ".api_request") as api_mock:
                try:
                    preflight()
                except (Rejected, RuntimeError):
                    pass
                else:
                    raise AssertionError("historical attempt or unavailable history was accepted")
                api_mock.assert_not_called()

    with tempfile.TemporaryDirectory() as temporary_directory:
        target = Path(temporary_directory) / "source" / ALLOWLISTED_PATH
        target.parent.mkdir(parents=True)
        target.write_text("const x=1\n", encoding="utf-8")
        with patch.dict(os.environ, {"GH_TOKEN": "test-write-token"}, clear=False):
            with patch("subprocess.run") as run_mock:
                run_mock.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
                run_formatter("formatter.cjs", "trusted-config", str(target))
                passed_env = run_mock.call_args.kwargs["env"]
                assert "GH_TOKEN" not in passed_env and "GITHUB_TOKEN" not in passed_env
                run_mock.return_value = subprocess.CompletedProcess([], 1, stdout="", stderr="failure")
                try:
                    run_formatter("formatter.cjs", "trusted-config", str(target))
                except Rejected:
                    formatter_failed = True
                else:
                    formatter_failed = False
                assert formatter_failed

    publish_sha = "e" * 40
    publish_context = (run, pr, valid_authorization, [])
    publish_calls: list[tuple[str, str, dict[str, Any] | None]] = []
    base_tree_response = {
        "truncated": False,
        "tree": [
            {"path": ALLOWLISTED_PATH, "mode": "100644", "type": "blob", "sha": "1" * 40},
            {"path": "README.md", "mode": "100644", "type": "blob", "sha": "2" * 40},
        ],
    }
    repaired_tree_response = {
        "truncated": False,
        "tree": [
            {"path": ALLOWLISTED_PATH, "mode": "100644", "type": "blob", "sha": "b" * 40},
            {"path": "README.md", "mode": "100644", "type": "blob", "sha": "2" * 40},
        ],
    }

    def publish_api(method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        publish_calls.append((method, endpoint, kwargs.get("payload")))
        if endpoint.endswith(f"git/commits/{sha}"):
            return {"tree": {"sha": "f" * 40}}
        if endpoint.endswith(f"git/trees/{'f' * 40}?recursive=1"):
            return base_tree_response
        if endpoint.endswith(f"git/trees/{'c' * 40}?recursive=1"):
            return repaired_tree_response
        if endpoint.endswith("git/blobs"):
            return {"sha": "b" * 40}
        if endpoint.endswith("git/trees"):
            return {"sha": "c" * 40}
        if endpoint.endswith("git/commits"):
            return {"sha": publish_sha}
        if endpoint.endswith("git/refs/heads/fix/page-format"):
            return {"ref": "refs/heads/fix/page-format"}
        raise AssertionError(endpoint)

    with tempfile.TemporaryDirectory() as temporary_directory:
        artifact = Path(temporary_directory) / "page.tsx"
        artifact.write_bytes(b"export default function Page() { return null; }\n")
        publish_env = {
            "GH_TOKEN": "mock-token",
            "REPOSITORY": repository,
            "PR_NUMBER": "7",
            "EXPECTED_SHA": sha,
            "EXPECTED_HEAD_REF": "fix/page-format",
            "SOURCE_RUN_ID": "123",
            "AUTHORIZATION_COMMENT_ID": "99",
            "ARTIFACT_FILE": str(artifact),
            "ARTIFACT_SHA256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        }
        with patch.dict(os.environ, publish_env, clear=False), patch(
            __name__ + ".get_authorized_context", return_value=publish_context
        ) as context_mock, patch(__name__ + ".api_request", side_effect=publish_api), patch(
            __name__ + ".write_output"
        ) as output_mock:
            publish()
            assert context_mock.call_count == 2
            branch_updates = [call for call in publish_calls if call[0] == "PATCH"]
            assert len(branch_updates) == 1
            assert branch_updates[0][2] == {"sha": publish_sha, "force": False}
            tree_payloads = [call[2] for call in publish_calls if call[1].endswith("git/trees")]
            assert tree_payloads[0]["tree"] == [
                {"path": ALLOWLISTED_PATH, "mode": "100644", "type": "blob", "sha": "b" * 40}
            ]
            assert not any(
                method in {"POST", "PATCH", "PUT", "DELETE"}
                and ("/issues/" in endpoint or "/pulls/" in endpoint)
                for method, endpoint, _ in publish_calls
            )
            output_mock.assert_called_once_with({"repair_sha": publish_sha})

    repair_sha = "c" * 40
    dispatch_pr = {
        "state": "open",
        "draft": False,
        "base": {"ref": "main"},
        "head": {
            "sha": repair_sha,
            "ref": "fix/page-format",
            "repo": {"full_name": repository},
        },
    }
    successful_jobs = [{"name": name, "conclusion": "success"} for name in sorted(REQUIRED_JOBS)]
    dispatch_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def dispatch_api(method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        dispatch_calls.append((method, endpoint, kwargs.get("payload")))
        if endpoint.endswith("/pulls/7"):
            return dispatch_pr
        if endpoint.endswith("/actions/runs/555"):
            return {"head_sha": repair_sha, "status": "completed"}
        if endpoint.endswith("/actions/runs/555/jobs?per_page=100"):
            return {"jobs": successful_jobs}
        if method == "POST":
            return {}
        raise AssertionError(endpoint)

    dispatch_env = {
        "GH_TOKEN": "mock-token",
        "REPOSITORY": repository,
        "PR_NUMBER": "7",
        "EXPECTED_REPAIR_SHA": repair_sha,
        "SOURCE_RUN_ID": "123",
        "CI_WORKFLOW_ID": "10",
    }
    run_lists = [[{"id": 444}], [{"id": 444}, {"id": 555, "head_sha": repair_sha, "event": "workflow_dispatch"}]]
    dispatch_outputs: list[dict[str, str]] = []
    with patch.dict(os.environ, dispatch_env, clear=False), patch(
        __name__ + ".api_request", side_effect=dispatch_api
    ), patch(__name__ + ".paginated", side_effect=run_lists), patch(
        __name__ + ".write_output", side_effect=dispatch_outputs.append
    ), patch(__name__ + ".time.sleep"):
        dispatch_ci()
    assert sum(call[0] == "POST" for call in dispatch_calls) == 1
    assert dispatch_outputs[-1] == {
        "fresh_ci_run_id": "555",
        "fresh_ci_sha": repair_sha,
        "fresh_ci_result": "success",
    }

    stale_pr = {**dispatch_pr, "head": {**dispatch_pr["head"], "sha": "d" * 40}}
    stale_dispatch_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def stale_dispatch_api(method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        stale_dispatch_calls.append((method, endpoint, kwargs.get("payload")))
        return stale_pr

    with patch.dict(os.environ, dispatch_env, clear=False), patch(
        __name__ + ".api_request", side_effect=stale_dispatch_api
    ):
        try:
            dispatch_ci()
        except Rejected as error:
            assert str(error) == "PR-head-changed-before-fresh-CI-dispatch"
        else:
            raise AssertionError("stale PR head was dispatched")
    assert not any(call[0] == "POST" for call in stale_dispatch_calls)

    successful_jobs[0] = {**successful_jobs[0], "conclusion": "failure"}
    failed_check_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def failed_check_api(method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        failed_check_calls.append((method, endpoint, kwargs.get("payload")))
        return dispatch_api(method, endpoint, **kwargs)

    with patch.dict(os.environ, dispatch_env, clear=False), patch(
        __name__ + ".api_request", side_effect=failed_check_api
    ), patch(__name__ + ".paginated", side_effect=run_lists), patch(
        __name__ + ".time.sleep"
    ):
        try:
            dispatch_ci()
        except Rejected as error:
            assert str(error) == "fresh-CI-required-checks-not-all-successful"
        else:
            raise AssertionError("failed fresh CI checks were accepted")
    assert sum(call[0] == "POST" for call in failed_check_calls) == 1

    mismatch_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def mismatch_api(method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        mismatch_calls.append((method, endpoint, kwargs.get("payload")))
        if endpoint.endswith("/pulls/7"):
            return dispatch_pr
        if endpoint.endswith("/actions/runs/555"):
            return {"head_sha": "d" * 40, "status": "completed"}
        if method == "POST":
            return {}
        raise AssertionError(endpoint)

    with patch.dict(os.environ, dispatch_env, clear=False), patch(
        __name__ + ".api_request", side_effect=mismatch_api
    ), patch(__name__ + ".paginated", side_effect=run_lists), patch(__name__ + ".time.sleep"):
        try:
            dispatch_ci()
        except Rejected as error:
            assert str(error) == "fresh-CI-run-SHA-mismatch"
        else:
            raise AssertionError("fresh CI run detail with a different SHA was accepted")
    assert sum(call[0] == "POST" for call in mismatch_calls) == 1

    wrong_sha_lists = [
        [{"id": 444}],
        [{"id": 444}, {"id": 556, "head_sha": "d" * 40, "event": "workflow_dispatch"}],
    ]
    with patch.dict(os.environ, dispatch_env, clear=False), patch(
        __name__ + ".api_request", side_effect=dispatch_api
    ), patch(__name__ + ".paginated", side_effect=wrong_sha_lists), patch(
        __name__ + ".time.monotonic", side_effect=[0, 181]
    ), patch(__name__ + ".time.sleep"):
        try:
            dispatch_ci()
        except Rejected as error:
            assert str(error) == "fresh-CI-dispatch-not-observed-on-repair-SHA"
        else:
            raise AssertionError("fresh CI on a different SHA was accepted")

    event_directory.cleanup()
    print(f"Repair self-tests passed: {len(rejected)} rejected eligibility cases, exact authorization history, read-only preflight, one-file tree enforcement, formatter credential isolation, fresh-CI SHA/check validation")


def main() -> None:
    if "--self-test" in sys.argv:
        self_test()
        return
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "preflight",
            "verify-source",
            "format-file",
            "verify-working-tree",
            "verify-artifact",
            "publish",
            "dispatch-ci",
        ),
    )
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            preflight()
        elif args.command == "verify-source":
            verify_source_command(args)
        elif args.command == "format-file":
            run_formatter(required_env("FORMATTER"), required_env("TRUSTED_CONFIG"), required_env("TARGET_FILE"))
        elif args.command == "verify-working-tree":
            verify_working_tree()
        elif args.command == "verify-artifact":
            digest = verify_formatted_content(
                required_env("FORMATTER"), required_env("TRUSTED_CONFIG"), required_env("ARTIFACT_FILE")
            )
            write_output({"artifact_sha256": digest})
        elif args.command == "publish":
            publish()
        elif args.command == "dispatch-ci":
            dispatch_ci()
    except (Rejected, OSError, ValueError, urllib.error.URLError, KeyError, json.JSONDecodeError) as error:
        print(f"Repair stopped safely: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()