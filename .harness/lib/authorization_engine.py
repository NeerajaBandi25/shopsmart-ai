import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import yaml


class RiskClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    DRAFT = "DRAFT"
    WRITE = "WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"


class SessionMode(str, Enum):
    MANUAL = "MANUAL"
    AUTONOMOUS_DEV = "AUTONOMOUS_DEV"
    READ_ONLY_AUTO = "READ_ONLY_AUTO"

    @classmethod
    def from_environment(cls) -> "SessionMode":
        raw = os.getenv("SHOPSMART_SESSION_MODE", "READ_ONLY_AUTO").strip().upper()
        try:
            return cls(raw)
        except ValueError:
            return cls.READ_ONLY_AUTO


class OperationType(str, Enum):
    READ = "READ"
    DRAFT = "DRAFT"
    WRITE = "WRITE"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRES_HUMAN_APPROVAL = "REQUIRES_HUMAN_APPROVAL"


class ConfigurationError(Exception):
    """Raised when authorization configuration is invalid or tampered with."""
    pass


VALID_RISK_CLASSES: Set[str] = {rc.value for rc in RiskClass}
VALID_OPERATION_TYPES: Set[str] = {op.value for op in OperationType}
VALID_DECISIONS: Set[str] = {d.value for d in Decision}


def _match_glob(path_str: str, pattern: str) -> bool:
    """
    Match a relative POSIX path against a glob pattern supporting ** wildcards.
    """
    path_str = path_str.replace("\\", "/").strip("/")
    pattern = pattern.replace("\\", "/").strip("/")

    parts = pattern.split("/")
    regex_parts = []
    for part in parts:
        if part == "**":
            regex_parts.append(".*")
        else:
            p = re.escape(part).replace(r"\*", r"[^/]*").replace(r"\?", r"[^/]")
            regex_parts.append(p)

    rx = "/".join(regex_parts)
    rx = rx.replace("/.*/", "(?:/.*/|/)")
    rx = rx.replace(".*/", "(?:.*/)?")
    rx = rx.replace("/.*", "(?:/.*)?")
    return bool(re.match(r"^" + rx + r"$", path_str, re.IGNORECASE))


class ToolDefinition:
    def __init__(
        self,
        name: str,
        risk_class: RiskClass,
        operation_type: OperationType,
        allow_patterns: List[str],
        deny_patterns: List[str],
        timeout_ms: int = 5000,
        input_schema: Optional[str] = None,
        output_schema: Optional[str] = None,
        retry_policy: Optional[Dict[str, Any]] = None,
        audit_policy: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.risk_class = risk_class
        self.operation_type = operation_type
        self.allow_patterns = allow_patterns
        self.deny_patterns = deny_patterns
        self.timeout_ms = timeout_ms
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.retry_policy = retry_policy or {}
        self.audit_policy = audit_policy or {}


class AuthorizationEngine:
    def __init__(
        self,
        risk_classes: Dict[str, Any],
        permission_matrix: Dict[str, Dict[str, str]],
        tools: Dict[str, ToolDefinition],
        protected_files: Optional[List[str]] = None,
        session_overrides: Optional[Dict[str, Any]] = None,
        persisted_mode: Optional[str] = None,
    ):
        self.risk_classes = risk_classes
        self.permission_matrix = permission_matrix
        self.tools = tools
        self.protected_files = protected_files or []
        self.session_overrides = session_overrides or {}
        self.persisted_mode = persisted_mode

    @classmethod
    def from_directory(cls, policy_dir: Union[str, Path]) -> "AuthorizationEngine":
        policy_path = Path(policy_dir).resolve()
        if not policy_path.is_dir():
            raise ConfigurationError(f"Policy directory not found: {policy_path}")

        risk_classes_file = policy_path / "risk-classes.yaml"
        matrix_file = policy_path / "permission-matrix.yaml"
        registry_file = policy_path / "tool-registry.yaml"
        protected_files_file = policy_path / "protected-files.txt"
        session_overrides_file = policy_path / "session-overrides.yaml"

        for required_file in (risk_classes_file, matrix_file, registry_file):
            if not required_file.is_file():
                raise ConfigurationError(f"Required policy file missing: {required_file}")

        try:
            with open(risk_classes_file, "r", encoding="utf-8") as f:
                risk_data = yaml.safe_load(f) or {}
            with open(matrix_file, "r", encoding="utf-8") as f:
                matrix_data = yaml.safe_load(f) or {}
            with open(registry_file, "r", encoding="utf-8") as f:
                registry_data = yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigurationError(f"Failed to parse policy YAML: {e}") from e

        session_overrides = {}
        if session_overrides_file.is_file():
            try:
                with open(session_overrides_file, "r", encoding="utf-8") as f:
                    session_overrides = yaml.safe_load(f) or {}
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to parse session overrides: {e}"
                ) from e

        protected_files = []
        if protected_files_file.is_file():
            try:
                with open(protected_files_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            protected_files.append(line)
            except Exception as e:
                raise ConfigurationError(f"Failed to read protected files: {e}") from e

        # Load persisted session mode from state directory
        persisted_mode = None
        state_dir = policy_path.parent / "state"
        mode_file = state_dir / "session_mode.json"
        if mode_file.is_file():
            try:
                with open(mode_file, "r", encoding="utf-8") as f:
                    mode_data = yaml.safe_load(f) or {}
                    persisted_mode = mode_data.get("mode")
                    # Validate the persisted mode
                    if persisted_mode:
                        persisted_mode = persisted_mode.strip().upper()
                        valid_modes = {mode.value for mode in SessionMode}
                        if persisted_mode not in valid_modes:
                            persisted_mode = None  # Invalid mode, will fall back to default
            except Exception:
                # If we can't read the persisted mode, continue without it
                persisted_mode = None

        return cls.from_dict(
            risk_classes_data=risk_data,
            permission_matrix_data=matrix_data,
            tool_registry_data=registry_data,
            protected_files=protected_files,
            session_overrides=session_overrides,
            persisted_mode=persisted_mode,
        )

    @classmethod
    def from_dict(
        cls,
        risk_classes_data: Dict[str, Any],
        permission_matrix_data: Dict[str, Any],
        tool_registry_data: Dict[str, Any],
        protected_files: Optional[List[str]] = None,
        session_overrides: Optional[Dict[str, Any]] = None,
        persisted_mode: Optional[str] = None,
    ) -> "AuthorizationEngine":
        # 1. Validate risk classes
        raw_risk_classes = risk_classes_data.get("risk_classes")
        if not isinstance(raw_risk_classes, dict):
            raise ConfigurationError("risk_classes must be a dictionary")

        if set(raw_risk_classes.keys()) != VALID_RISK_CLASSES:
            raise ConfigurationError(
                f"risk_classes must contain exactly {VALID_RISK_CLASSES}, got {set(raw_risk_classes.keys())}"
            )

        # 2. Validate permission matrix
        raw_matrix = permission_matrix_data.get("permission_matrix")
        if not isinstance(raw_matrix, dict):
            raise ConfigurationError("permission_matrix must be a dictionary")

        if set(raw_matrix.keys()) != VALID_RISK_CLASSES:
            raise ConfigurationError(
                f"permission_matrix must define rows for all risk classes {VALID_RISK_CLASSES}"
            )

        matrix: Dict[str, Dict[str, str]] = {}
        for risk_cls, op_dict in raw_matrix.items():
            if not isinstance(op_dict, dict):
                raise ConfigurationError(f"Row {risk_cls} in permission_matrix must be a dict")

            # Every operation type must be defined with a valid decision
            for op_name, decision_val in op_dict.items():
                if op_name not in VALID_OPERATION_TYPES:
                    raise ConfigurationError(
                        f"Invalid operation type '{op_name}' in permission matrix row '{risk_cls}'"
                    )
                if decision_val not in VALID_DECISIONS:
                    raise ConfigurationError(
                        f"Invalid decision '{decision_val}' in permission matrix for {risk_cls}.{op_name}"
                    )

            # Ensure all operations exist in matrix for this class
            if set(op_dict.keys()) != VALID_OPERATION_TYPES:
                raise ConfigurationError(
                    f"Permission matrix for {risk_cls} must define all operation types {VALID_OPERATION_TYPES}"
                )

            matrix[risk_cls] = {k: str(v) for k, v in op_dict.items()}

        # 3. Validate tool registry
        raw_tools = tool_registry_data.get("tools")
        if not isinstance(raw_tools, dict):
            raise ConfigurationError("tools in tool_registry must be a dictionary")

        required_tool_fields = {
            "risk_class",
            "operation_type",
            "input_schema",
            "output_schema",
            "resource_scope",
            "timeout_ms",
            "retry_policy",
            "audit_policy",
        }

        tools: Dict[str, ToolDefinition] = {}
        for tool_name, tool_cfg in raw_tools.items():
            if not isinstance(tool_cfg, dict):
                raise ConfigurationError(f"Tool configuration for '{tool_name}' must be a dict")

            missing_fields = required_tool_fields - set(tool_cfg.keys())
            if missing_fields:
                raise ConfigurationError(
                    f"Tool '{tool_name}' missing required policy metadata: {sorted(missing_fields)}"
                )

            risk_class_str = tool_cfg["risk_class"]
            op_type_str = tool_cfg["operation_type"]
            input_schema = tool_cfg["input_schema"]
            output_schema = tool_cfg["output_schema"]
            resource_scope = tool_cfg["resource_scope"]
            timeout_ms = tool_cfg["timeout_ms"]
            retry_policy = tool_cfg["retry_policy"]
            audit_policy = tool_cfg["audit_policy"]

            if not isinstance(risk_class_str, str) or risk_class_str not in VALID_RISK_CLASSES:
                raise ConfigurationError(
                    f"Tool '{tool_name}' has invalid risk_class: '{risk_class_str}'"
                )

            if not isinstance(op_type_str, str) or op_type_str not in VALID_OPERATION_TYPES:
                raise ConfigurationError(
                    f"Tool '{tool_name}' has invalid operation_type: '{op_type_str}'"
                )

            if not isinstance(input_schema, str) or not input_schema.strip():
                raise ConfigurationError(
                    f"Tool '{tool_name}' input_schema must be a non-empty string"
                )

            if not isinstance(output_schema, str) or not output_schema.strip():
                raise ConfigurationError(
                    f"Tool '{tool_name}' output_schema must be a non-empty string"
                )

            if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms <= 0:
                raise ConfigurationError(
                    f"Tool '{tool_name}' timeout_ms must be a positive integer, got {timeout_ms}"
                )

            if not isinstance(resource_scope, dict):
                raise ConfigurationError(
                    f"Tool '{tool_name}' resource_scope must be a dictionary"
                )

            allow_patterns = resource_scope.get("allow")
            deny_patterns = resource_scope.get("deny")
            if not isinstance(allow_patterns, list) or not isinstance(deny_patterns, list):
                raise ConfigurationError(
                    f"Tool '{tool_name}' resource_scope must contain 'allow' and 'deny' lists"
                )

            if not all(isinstance(p, str) for p in allow_patterns):
                raise ConfigurationError(
                    f"Tool '{tool_name}' resource_scope allow patterns must all be strings"
                )

            if not all(isinstance(p, str) for p in deny_patterns):
                raise ConfigurationError(
                    f"Tool '{tool_name}' resource_scope deny patterns must all be strings"
                )

            if not isinstance(retry_policy, dict):
                raise ConfigurationError(
                    f"Tool '{tool_name}' retry_policy must be a mapping"
                )

            if not isinstance(audit_policy, dict):
                raise ConfigurationError(
                    f"Tool '{tool_name}' audit_policy must be a mapping"
                )

            tools[tool_name] = ToolDefinition(
                name=tool_name,
                risk_class=RiskClass(risk_class_str),
                operation_type=OperationType(op_type_str),
                allow_patterns=allow_patterns,
                deny_patterns=deny_patterns,
                timeout_ms=timeout_ms,
                input_schema=input_schema.strip(),
                output_schema=output_schema.strip(),
                retry_policy=retry_policy,
                audit_policy=audit_policy,
            )

        normalized_overrides = (
            session_overrides if isinstance(session_overrides, dict) else {}
        )

        raw_session_overrides = normalized_overrides.get(
            "session_overrides", {}
        )

        if not isinstance(raw_session_overrides, dict):
            raise ConfigurationError(
                "session_overrides must be a dictionary"
            )

        valid_modes = {mode.value for mode in SessionMode}

        for mode_name, mode_cfg in raw_session_overrides.items():
            if mode_name not in valid_modes:
                raise ConfigurationError(
                    f"Unknown session mode: '{mode_name}'"
                )

            if not isinstance(mode_cfg, dict):
                raise ConfigurationError(
                    f"Session mode '{mode_name}' must be a dictionary"
                )

            tools_cfg = mode_cfg.get("tools", {})

            if not isinstance(tools_cfg, dict):
                raise ConfigurationError(
                    f"Session mode '{mode_name}.tools' must be a dictionary"
                )

            for tool_name, decision in tools_cfg.items():
                if tool_name not in tools:
                    raise ConfigurationError(
                        f"Session override references unknown tool: '{tool_name}'"
                    )

                if decision not in VALID_DECISIONS:
                    raise ConfigurationError(
                        f"Invalid session decision '{decision}'"
                    )

        return cls(
            risk_classes=raw_risk_classes,
            permission_matrix=matrix,
            tools=tools,
            protected_files=protected_files,
            session_overrides=normalized_overrides,
            persisted_mode=persisted_mode,
        )

    def resolve_permission(
        self,
        risk_class: Union[RiskClass, str],
        operation_type: Union[OperationType, str],
    ) -> Decision:
        rc_key = risk_class.value if isinstance(risk_class, RiskClass) else str(risk_class)
        op_key = operation_type.value if isinstance(operation_type, OperationType) else str(operation_type)

        matrix_row = self.permission_matrix.get(rc_key)
        if not matrix_row:
            return Decision.DENY

        decision_str = matrix_row.get(op_key)
        if not decision_str:
            return Decision.DENY

        try:
            return Decision(decision_str)
        except ValueError:
            return Decision.DENY

    def _resolve_session_override(
        self,
        tool_name: str,
        session_mode: SessionMode,
    ) -> Optional[Decision]:
        raw = self.session_overrides.get("session_overrides", {})

        if not isinstance(raw, dict):
            return None

        mode_cfg = raw.get(session_mode.value, {})

        if not isinstance(mode_cfg, dict):
            return None

        tools_cfg = mode_cfg.get("tools", {})

        if not isinstance(tools_cfg, dict):
            return None

        value = tools_cfg.get(tool_name)

        if value is None:
            return None

        try:
            return Decision(value)
        except ValueError:
            return Decision.DENY

    def authorize(
        self,
        tool_name: str,
        invocation_input: Dict[str, Any],
        repo_root: Union[str, Path],
        session_mode: Optional[Union[SessionMode, str]] = None,
    ) -> Decision:
        # Resolve explicit session mode or environment mode or persisted mode.
        if session_mode is None:
            # Check for persisted mode first
            if self.persisted_mode:
                try:
                    active_mode = SessionMode(self.persisted_mode)
                except ValueError:
                    # If persisted mode is invalid, fall back to environment
                    active_mode = SessionMode.from_environment()
            else:
                # No persisted mode, use environment variable
                active_mode = SessionMode.from_environment()
        elif isinstance(session_mode, SessionMode):
            active_mode = session_mode
        else:
            try:
                active_mode = SessionMode(str(session_mode).upper())
            except ValueError:
                return Decision.DENY

        # 1. Look up tool in registry.
        tool = self.tools.get(tool_name)
        if not tool:
            return Decision.DENY

        # 2. Check base permission matrix decision
        base_decision = self.resolve_permission(tool.risk_class, tool.operation_type)
        if base_decision == Decision.DENY:
            return Decision.DENY

        # 3. Check protected files for non-read operations
        root_path = Path(repo_root).resolve()

        # 4. Extract path targets from invocation input
        target_paths = self._extract_target_paths(invocation_input)

        # If no paths involved, return base decision
        if not target_paths:
            return base_decision

        # 5. Check each target path against resource scope & security rules
        for raw_path in target_paths:
            # Check for path traversal / outside repo root
            canonical_rel_path = self._canonicalize_and_check_traversal(raw_path, root_path)
            if canonical_rel_path is None:
                return Decision.DENY

            # Check protected files for non-read operations
            if tool.operation_type != OperationType.READ:
                if self._is_protected(canonical_rel_path):
                    return Decision.DENY

            # Check tool deny patterns (deny takes precedence over allow)
            if any(_match_glob(canonical_rel_path, pattern) for pattern in tool.deny_patterns):
                return Decision.DENY

            # Check tool allow patterns
            if tool.allow_patterns:
                if not any(_match_glob(canonical_rel_path, pattern) for pattern in tool.allow_patterns):
                    return Decision.DENY

        session_decision = self._resolve_session_override(
            tool_name,
            active_mode,
        )

        if session_decision is not None:
            return session_decision

        return base_decision

    def _extract_target_paths(self, invocation_input: Dict[str, Any]) -> List[str]:
        paths = []
        for key in ("path", "file_path", "target", "file", "filename"):
            val = invocation_input.get(key)
            if isinstance(val, str) and val.strip():
                paths.append(val.strip())

        for key in ("paths", "files", "targets"):
            val = invocation_input.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item.strip():
                        paths.append(item.strip())
        return paths

    def _canonicalize_and_check_traversal(
        self,
        raw_path: str,
        repo_root: Path,
    ) -> Optional[str]:
        try:
            # Normalize slashes
            normalized = raw_path.replace("\\", "/").strip()

            # Check explicit traversal tokens
            parts = normalized.split("/")
            if ".." in parts:
                return None

            path_obj = Path(normalized)
            if path_obj.is_absolute():
                resolved = path_obj.resolve()
            else:
                resolved = (repo_root / path_obj).resolve()

            # Ensure resolved path is inside repo_root
            try:
                rel = resolved.relative_to(repo_root)
            except ValueError:
                return None

            return rel.as_posix()
        except Exception:
            return None

    def _is_protected(self, rel_path: str) -> bool:
        for protected in self.protected_files:
            clean_protected = protected.strip().replace("\\", "/").rstrip("/")
            if not clean_protected:
                continue
            if rel_path == clean_protected or rel_path.startswith(clean_protected + "/"):
                return True
            if (
                _match_glob(rel_path, clean_protected)
                or _match_glob(rel_path, clean_protected + "/*")
                or _match_glob(rel_path, clean_protected + "/**")
            ):
                return True
        return False
