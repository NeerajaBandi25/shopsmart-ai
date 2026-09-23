import os
from pathlib import Path

from lib.authorization_engine import (
    AuthorizationEngine,
    Decision,
    SessionMode,
)


HARNESS_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = HARNESS_ROOT.parent
POLICIES_DIR = HARNESS_ROOT / "policies" / "trusted"


def get_engine():
    return AuthorizationEngine.from_directory(POLICIES_DIR)


def test_manual_mode_preserves_existing_write_approval():
    engine = get_engine()

    decision = engine.authorize(
        "apply_patch",
        {"path": "backend/src/services/auth_service.py"},
        REPO_ROOT,
        SessionMode.MANUAL,
    )

    assert decision == Decision.REQUIRES_HUMAN_APPROVAL


def test_autonomous_mode_allows_permitted_application_write():
    engine = get_engine()

    decision = engine.authorize(
        "apply_patch",
        {"path": "backend/src/services/auth_service.py"},
        REPO_ROOT,
        SessionMode.AUTONOMOUS_DEV,
    )

    assert decision == Decision.ALLOW


def test_autonomous_mode_does_not_bypass_main_py_deny():
    engine = get_engine()

    decision = engine.authorize(
        "apply_patch",
        {"path": "backend/src/main.py"},
        REPO_ROOT,
        SessionMode.AUTONOMOUS_DEV,
    )

    assert decision == Decision.DENY


def test_autonomous_mode_does_not_bypass_frontend_api_client_deny():
    engine = get_engine()

    decision = engine.authorize(
        "apply_patch",
        {"path": "frontend/src/lib/api-client.ts"},
        REPO_ROOT,
        SessionMode.AUTONOMOUS_DEV,
    )

    assert decision == Decision.DENY


def test_autonomous_mode_cannot_modify_trusted_policy():
    engine = get_engine()

    decision = engine.authorize(
        "apply_patch",
        {"path": ".harness/policies/trusted/tool-registry.yaml"},
        REPO_ROOT,
        SessionMode.AUTONOMOUS_DEV,
    )

    assert decision == Decision.DENY


def test_autonomous_mode_cannot_modify_git():
    engine = get_engine()

    decision = engine.authorize(
        "apply_patch",
        {"path": ".git/config"},
        REPO_ROOT,
        SessionMode.AUTONOMOUS_DEV,
    )

    assert decision == Decision.DENY


def test_autonomous_mode_cannot_traverse_outside_repository():
    engine = get_engine()

    decision = engine.authorize(
        "apply_patch",
        {"path": "../outside.txt"},
        REPO_ROOT,
        SessionMode.AUTONOMOUS_DEV,
    )

    assert decision == Decision.DENY


def test_autonomous_mode_preserves_read_access():
    engine = get_engine()

    decision = engine.authorize(
        "read_file",
        {"path": "backend/src/services/auth_service.py"},
        REPO_ROOT,
        SessionMode.AUTONOMOUS_DEV,
    )

    assert decision == Decision.ALLOW


def test_environment_autonomous_mode_is_opt_in():
    engine = get_engine()

    previous = os.environ.get("SHOPSMART_SESSION_MODE")

    try:
        os.environ.pop("SHOPSMART_SESSION_MODE", None)

        manual_decision = engine.authorize(
            "apply_patch",
            {"path": "backend/src/services/auth_service.py"},
            REPO_ROOT,
        )

        assert manual_decision == Decision.REQUIRES_HUMAN_APPROVAL

        os.environ["SHOPSMART_SESSION_MODE"] = "AUTONOMOUS_DEV"

        autonomous_decision = engine.authorize(
            "apply_patch",
            {"path": "backend/src/services/auth_service.py"},
            REPO_ROOT,
        )

        assert autonomous_decision == Decision.ALLOW

    finally:
        if previous is None:
            os.environ.pop("SHOPSMART_SESSION_MODE", None)
        else:
            os.environ["SHOPSMART_SESSION_MODE"] = previous


def test_invalid_environment_mode_fails_closed_to_manual():
    engine = get_engine()

    previous = os.environ.get("SHOPSMART_SESSION_MODE")

    try:
        os.environ["SHOPSMART_SESSION_MODE"] = "INVALID_MODE"

        decision = engine.authorize(
            "apply_patch",
            {"path": "backend/src/services/auth_service.py"},
            REPO_ROOT,
        )

        assert decision == Decision.REQUIRES_HUMAN_APPROVAL

    finally:
        if previous is None:
            os.environ.pop("SHOPSMART_SESSION_MODE", None)
        else:
            os.environ["SHOPSMART_SESSION_MODE"] = previous


def test_session_overlay_references_only_known_tool():
    engine = get_engine()

    assert "AUTONOMOUS_DEV" in engine.session_overrides["session_overrides"]
    assert (
        engine.session_overrides["session_overrides"]["AUTONOMOUS_DEV"]["tools"]
        == {"apply_patch": "ALLOW"}
    )
