"""Offline contract checks for the production deployment workflow."""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-production.yml"
VERCEL_CONFIG = ROOT / "frontend" / "vercel.json"
REQUIRED_CHECKS = (
    "Backend tests (pytest, PostgreSQL)",
    "Backend security gates (Ruff, pip-audit)",
    "Frontend tests (jest, lint, prettier)",
    "Docker Compose smoke test",
)


class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        cls.deploy_workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        cls.vercel_config = json.loads(VERCEL_CONFIG.read_text(encoding="utf-8"))

    def test_required_ci_check_names_remain_exactly_once(self) -> None:
        for check_name in REQUIRED_CHECKS:
            with self.subTest(check_name=check_name):
                self.assertEqual(
                    len(
                        re.findall(
                            rf"^\s+name: {re.escape(check_name)}$",
                            self.ci_workflow,
                            re.M,
                        )
                    ),
                    1,
                )

    def test_backend_ci_executes_real_redis_runtime_checks(self) -> None:
        self.assertRegex(self.ci_workflow, r"(?m)^\s+redis:\n\s+image: redis:7-alpine$")
        self.assertIn('AI_RUNTIME_LIVE_TEST: "1"', self.ci_workflow)
        self.assertIn("tests/integration/test_ai_runtime_live.py", self.ci_workflow)
        self.assertIn("-k real_redis", self.ci_workflow)

    def test_production_workflow_is_manual_only_and_serialized(self) -> None:
        self.assertRegex(
            self.deploy_workflow,
            r"(?m)^on:\n\s+workflow_dispatch:\s*$",
        )
        self.assertNotRegex(self.deploy_workflow, r"(?m)^\s+(push|pull_request):")
        self.assertIn("permissions: {}", self.deploy_workflow)
        self.assertIn("cancel-in-progress: false", self.deploy_workflow)
        self.assertEqual(self.deploy_workflow.count("id-token: write"), 2)

    def test_deployments_wait_for_preflight_and_human_approval(self) -> None:
        self.assertRegex(
            self.deploy_workflow,
            r"(?ms)^  release-approval:\n.*?^      name: release-approval\n",
        )
        self.assertIn("needs: [preflight, release-approval]", self.deploy_workflow)
        self.assertIn(
            "needs: [preflight, release-approval, backend-deploy]", self.deploy_workflow
        )
        self.assertIn(
            "needs: [preflight, release-approval, backend-deploy, frontend-deploy]",
            self.deploy_workflow,
        )
        self.assertIn("if: github.ref == 'refs/heads/main'", self.deploy_workflow)

    def test_production_credentials_are_isolated_and_not_long_lived_aws_keys(
        self,
    ) -> None:
        self.assertNotIn("AWS_ACCESS_KEY_ID", self.deploy_workflow)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", self.deploy_workflow)
        self.assertNotIn("DATABASE_URL:", self.deploy_workflow)
        self.assertNotIn("SECRET_KEY:", self.deploy_workflow)
        self.assertIn("role-to-assume: ${{ vars.AWS_ROLE_ARN }}", self.deploy_workflow)
        self.assertIn("VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}", self.deploy_workflow)
        self.assertIn(
            "VERCEL_PROJECT_ID: ${{ vars.VERCEL_PROJECT_ID }}", self.deploy_workflow
        )
        self.assertIn(
            "VERCEL_PRODUCTION_URL must be an HTTPS origin.", self.deploy_workflow
        )

    def test_frontend_failure_and_cancellation_trigger_backend_rollback(self) -> None:
        self.assertIn("vercel rollback --non-interactive", self.deploy_workflow)
        self.assertIn("cancelled()", self.deploy_workflow)
        self.assertIn("needs.frontend-deploy.result != 'success'", self.deploy_workflow)
        self.assertIn("steps.rollback.outputs.rollback_succeeded", self.deploy_workflow)
        self.assertIn("needs.backend-deploy.result != 'success'", self.deploy_workflow)
        self.assertIn(
            "python3 .github/scripts/deploy_ecs.py rollback", self.deploy_workflow
        )

    def test_vercel_health_checks_require_exact_http_200(self) -> None:
        self.assertGreaterEqual(self.deploy_workflow.count('!= "200"'), 3)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", self.deploy_workflow)

    def test_deployment_configuration_contains_no_account_ids_or_aws_keys(self) -> None:
        checked_files = (
            CI_WORKFLOW,
            DEPLOY_WORKFLOW,
            Path(__file__).resolve(),
            ROOT / ".github" / "scripts" / "deploy_preflight.py",
            ROOT / ".github" / "scripts" / "deploy_ecs.py",
            ROOT / "AWS_DEPLOYMENT.md",
            VERCEL_CONFIG,
        )
        for path in checked_files:
            with self.subTest(path=path.relative_to(ROOT)):
                content = path.read_text(encoding="utf-8")
                self.assertNotRegex(content, r"(?<!\d)\d{12}(?!\d)")
                self.assertNotRegex(content, r"\bAKIA[0-9A-Z]{16}\b")

    def test_vercel_git_deployments_are_disabled(self) -> None:
        git_config = self.vercel_config.get("git")
        self.assertIsInstance(git_config, dict)
        self.assertIs(git_config.get("deploymentEnabled"), False)


def self_test() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WorkflowContractTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        raise SystemExit(self_test())
    print("Run this workflow contract checker with --self-test", file=sys.stderr)
    raise SystemExit(2)
