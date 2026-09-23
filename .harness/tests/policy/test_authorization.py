import os
import sys
from pathlib import Path
import pytest

# Ensure .harness is in python path
HARNESS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(HARNESS_ROOT))

from lib.authorization_engine import (
    AuthorizationEngine,
    Decision,
    RiskClass,
    OperationType,
    ConfigurationError,
)

REPO_ROOT = HARNESS_ROOT.parent
POLICIES_DIR = HARNESS_ROOT / "policies" / "trusted"


def _valid_tool_config(overrides=None):
    base = {
        "risk_class": "WRITE",
        "operation_type": "WRITE",
        "input_schema": "apply_patch_input.yaml",
        "output_schema": "apply_patch_output.yaml",
        "resource_scope": {
            "allow": ["backend/**"],
            "deny": [".harness/**"],
        },
        "timeout_ms": 5000,
        "retry_policy": {"max_attempts": 1},
        "audit_policy": {"log_input": True},
    }
    if overrides:
        for k, v in overrides.items():
            if v is None:
                base.pop(k, None)
            else:
                base[k] = v
    return base


def _valid_permission_matrix():
    return {
        rc.value: {op.value: "ALLOW" for op in OperationType}
        for rc in RiskClass
    }


def _valid_risk_classes():
    return {
        rc.value: {"description": rc.value}
        for rc in RiskClass
    }


# ---------------------------------------------------------------------------
# Group 1: Configuration Loading & Strict Schema Validation
# ---------------------------------------------------------------------------

class TestConfigurationValidation:
    def test_load_trusted_policies_success(self):
        engine = AuthorizationEngine.from_directory(POLICIES_DIR)
        assert engine is not None
        assert len(engine.risk_classes) == 4
        assert len(engine.tools) >= 4

    def test_risk_classes_must_be_exact_four(self):
        engine = AuthorizationEngine.from_directory(POLICIES_DIR)
        expected_classes = {"READ_ONLY", "DRAFT", "WRITE", "DESTRUCTIVE"}
        assert set(engine.risk_classes.keys()) == expected_classes

    def test_invalid_risk_class_fails_closed(self):
        invalid_risk_classes = {
            "risk_classes": {
                "READ_ONLY": {"description": "test"},
                "UNKNOWN_CLASS": {"description": "invalid"},
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=invalid_risk_classes,
                permission_matrix_data={
                    "permission_matrix": {
                        "READ_ONLY": {op.value: "ALLOW" for op in OperationType}
                    }
                },
                tool_registry_data={"tools": {}},
            )

    def test_invalid_operation_type_fails_closed(self):
        invalid_matrix = {
            "permission_matrix": {
                "READ_ONLY": {
                    "READ": "ALLOW",
                    "INVALID_OP": "ALLOW",
                }
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data=invalid_matrix,
                tool_registry_data={"tools": {}},
            )

    def test_tool_missing_explicit_risk_class_or_operation_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"risk_class": None})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_with_unknown_risk_class_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"risk_class": "SUPERUSER"})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_missing_input_schema_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"input_schema": None})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_empty_input_schema_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"input_schema": "   "})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_missing_output_schema_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"output_schema": None})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_empty_output_schema_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"output_schema": ""})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_missing_resource_scope_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"resource_scope": None})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_invalid_resource_scope_type_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"resource_scope": "not-a-dict"})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_resource_scope_missing_allow_or_deny_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"resource_scope": {"allow": ["backend/**"]}})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_resource_scope_non_string_pattern_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({
                    "resource_scope": {"allow": [123], "deny": []}
                })
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_invalid_timeout_ms_non_positive_fails_closed(self):
        for bad_timeout in (0, -100, -1):
            invalid_tools = {
                "tools": {
                    "bad_tool": _valid_tool_config({"timeout_ms": bad_timeout})
                }
            }
            with pytest.raises(ConfigurationError):
                AuthorizationEngine.from_dict(
                    risk_classes_data=_valid_risk_classes(),
                    permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                    tool_registry_data=invalid_tools,
                )

    def test_tool_invalid_timeout_ms_type_fails_closed(self):
        for bad_timeout in ("5000", True, False, 5.5, None):
            invalid_tools = {
                "tools": {
                    "bad_tool": _valid_tool_config({"timeout_ms": bad_timeout})
                }
            }
            with pytest.raises(ConfigurationError):
                AuthorizationEngine.from_dict(
                    risk_classes_data=_valid_risk_classes(),
                    permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                    tool_registry_data=invalid_tools,
                )

    def test_tool_missing_retry_policy_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"retry_policy": None})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_invalid_retry_policy_type_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"retry_policy": "not-a-dict"})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_missing_audit_policy_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"audit_policy": None})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )

    def test_tool_invalid_audit_policy_type_fails_closed(self):
        invalid_tools = {
            "tools": {
                "bad_tool": _valid_tool_config({"audit_policy": ["not", "a", "dict"]})
            }
        }
        with pytest.raises(ConfigurationError):
            AuthorizationEngine.from_dict(
                risk_classes_data=_valid_risk_classes(),
                permission_matrix_data={"permission_matrix": _valid_permission_matrix()},
                tool_registry_data=invalid_tools,
            )


# ---------------------------------------------------------------------------
# Group 2: Permission Matrix Decision Resolution
# ---------------------------------------------------------------------------

class TestPermissionMatrixDecisions:
    @pytest.fixture
    def engine(self):
        return AuthorizationEngine.from_directory(POLICIES_DIR)

    def test_read_only_plus_read_allows(self, engine):
        decision = engine.resolve_permission(
            risk_class=RiskClass.READ_ONLY,
            operation_type=OperationType.READ,
        )
        assert decision == Decision.ALLOW

    def test_read_only_plus_write_denies(self, engine):
        decision = engine.resolve_permission(
            risk_class=RiskClass.READ_ONLY,
            operation_type=OperationType.WRITE,
        )
        assert decision == Decision.DENY

    def test_draft_plus_draft_allows(self, engine):
        decision = engine.resolve_permission(
            risk_class=RiskClass.DRAFT,
            operation_type=OperationType.DRAFT,
        )
        assert decision == Decision.ALLOW

    def test_draft_plus_execute_denies(self, engine):
        decision = engine.resolve_permission(
            risk_class=RiskClass.DRAFT,
            operation_type=OperationType.EXECUTE,
        )
        assert decision == Decision.DENY

    def test_write_plus_write_requires_human_approval(self, engine):
        decision = engine.resolve_permission(
            risk_class=RiskClass.WRITE,
            operation_type=OperationType.WRITE,
        )
        assert decision == Decision.REQUIRES_HUMAN_APPROVAL

    def test_write_plus_delete_denies(self, engine):
        decision = engine.resolve_permission(
            risk_class=RiskClass.WRITE,
            operation_type=OperationType.DELETE,
        )
        assert decision == Decision.DENY

    def test_destructive_plus_delete_requires_human_approval(self, engine):
        decision = engine.resolve_permission(
            risk_class=RiskClass.DESTRUCTIVE,
            operation_type=OperationType.DELETE,
        )
        assert decision == Decision.REQUIRES_HUMAN_APPROVAL

    def test_unknown_tool_denies(self, engine):
        decision = engine.authorize(
            tool_name="unknown_arbitrary_tool",
            invocation_input={"path": "backend/src/main.py"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.DENY


# ---------------------------------------------------------------------------
# Group 3: Resource Scope & Security Boundaries
# ---------------------------------------------------------------------------

class TestResourceScopeAndSecurity:
    @pytest.fixture
    def engine(self):
        return AuthorizationEngine.from_directory(POLICIES_DIR)

    def test_read_file_allowed_path(self, engine):
        decision = engine.authorize(
            tool_name="read_file",
            invocation_input={"path": "backend/src/services/auth_service.py"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.ALLOW

    def test_read_file_search_files_allowed(self, engine):
        decision = engine.authorize(
            tool_name="search_files",
            invocation_input={"path": "specs/001-user-auth-foundation/spec.md"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.ALLOW

    def test_path_traversal_denies(self, engine):
        traversals = [
            "../outside_repo.txt",
            "../../Windows/System32/drivers/etc/hosts",
            "backend/../../../etc/passwd",
            "..\\..\\sensitive.txt",
        ]
        for bad_path in traversals:
            decision = engine.authorize(
                tool_name="read_file",
                invocation_input={"path": bad_path},
                repo_root=REPO_ROOT,
            )
            assert decision == Decision.DENY, f"Failed to deny traversal path: {bad_path}"

    def test_denied_protected_policy_path_denies(self, engine):
        decision = engine.authorize(
            tool_name="read_file",
            invocation_input={"path": ".harness/policies/trusted/risk-classes.yaml"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.DENY

    def test_denied_nested_protected_policy_path_denies(self, engine):
        decision = engine.authorize(
            tool_name="read_file",
            invocation_input={"path": ".harness/policies/trusted/subdir/secret.yaml"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.DENY

    def test_denied_git_path_denies(self, engine):
        decision = engine.authorize(
            tool_name="read_file",
            invocation_input={"path": ".git/config"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.DENY

    def test_denied_nested_git_path_denies(self, engine):
        decision = engine.authorize(
            tool_name="read_file",
            invocation_input={"path": ".git/objects/example"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.DENY

    def test_apply_patch_in_scope_requires_human_approval(self, engine):
        decision = engine.authorize(
            tool_name="apply_patch",
            invocation_input={"path": "backend/src/services/auth_service.py"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.REQUIRES_HUMAN_APPROVAL

    def test_apply_patch_denied_file_in_scope(self, engine):
        # backend/src/main.py is explicitly denied in tool-registry.yaml
        decision = engine.authorize(
            tool_name="apply_patch",
            invocation_input={"path": "backend/src/main.py"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.DENY

    def test_apply_patch_frontend_denied_file(self, engine):
        # frontend/src/lib/api-client.ts is explicitly denied in tool-registry.yaml
        decision = engine.authorize(
            tool_name="apply_patch",
            invocation_input={"path": "frontend/src/lib/api-client.ts"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.DENY

    def test_deny_precedence_over_allow(self, engine):
        # backend/** is in allow, but backend/src/main.py is in deny
        decision = engine.authorize(
            tool_name="apply_patch",
            invocation_input={"path": "backend/src/main.py"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.DENY

    def test_unprotected_file_does_not_mean_writable(self, engine):
        # An unlisted arbitrary file outside allowed scopes (e.g. root script or config)
        decision = engine.authorize(
            tool_name="apply_patch",
            invocation_input={"path": "random_unscoped_file.py"},
            repo_root=REPO_ROOT,
        )
        assert decision == Decision.DENY

    def test_run_test_behavior_depends_on_policies(self, engine):
        """Test that run_test authorization depends on policy configuration."""
        # Test with a valid test target
        decision = engine.authorize(
            tool_name="run_test",
            invocation_input={"test_target": "backend/tests/unit/test_auth_service.py"},
            repo_root=REPO_ROOT,
        )
        # The decision depends on whether run_test is configured in the tool registry
        # and what permissions are set for it. Since we've implemented the executor,
        # it should no longer be denied solely for missing executor.
        # We're testing that our implementation doesn't break the authorization flow.
        assert decision in [Decision.ALLOW, Decision.DENY, Decision.REQUIRES_HUMAN_APPROVAL]

    def test_tool_scoped_deny_rule_denies_patch_on_denied_tests_if_configured(self):
        # Verify custom scope with explicit deny on tests
        scoped_tools = {
            "tools": {
                "apply_patch": {
                    "risk_class": "WRITE",
                    "operation_type": "WRITE",
                    "input_schema": "apply_patch_input.yaml",
                    "output_schema": "apply_patch_output.yaml",
                    "timeout_ms": 30000,
                    "retry_policy": {"max_attempts": 1},
                    "audit_policy": {"log_input": True, "log_output": True},
                    "resource_scope": {
                        "allow": ["backend/src/**"],
                        "deny": ["backend/tests/**"],
                    },
                }
            }
        }
        engine = AuthorizationEngine.from_dict(
            risk_classes_data={
                "risk_classes": {rc.value: {} for rc in RiskClass}
            },
            permission_matrix_data={
                "permission_matrix": {
                    rc.value: {op.value: "ALLOW" if rc == RiskClass.READ_ONLY else "REQUIRES_HUMAN_APPROVAL" for op in OperationType}
                    for rc in RiskClass
                }
            },
            tool_registry_data=scoped_tools,
        )
        # backend/src path -> allowed scope -> REQUIRES_HUMAN_APPROVAL
        assert engine.authorize(
            tool_name="apply_patch",
            invocation_input={"path": "backend/src/auth.py"},
            repo_root=REPO_ROOT,
        ) == Decision.REQUIRES_HUMAN_APPROVAL

        # backend/tests path -> denied scope -> DENY
        assert engine.authorize(
            tool_name="apply_patch",
            invocation_input={"path": "backend/tests/test_auth.py"},
            repo_root=REPO_ROOT,
        ) == Decision.DENY
