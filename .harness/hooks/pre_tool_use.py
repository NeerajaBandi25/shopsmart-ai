"""
PreToolUse Hook for Claude Code.

Enforces deterministic authorization decisions using AuthorizationEngine and ToolAdapter.
Outputs structured PreToolUse JSON to stdout.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

# Add .harness root to sys.path
HOOKS_DIR = Path(__file__).resolve().parent
HARNESS_ROOT = HOOKS_DIR.parent
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

from lib.authorization_engine import AuthorizationEngine, Decision, ConfigurationError
from lib.tool_adapter import normalize_tool_invocation


def build_response(
    decision: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Constructs the documented Claude Code PreToolUse response dictionary.
    """
    output: Dict[str, Any] = {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
    }
    if reason:
        output["permissionDecisionReason"] = reason
    return {"hookSpecificOutput": output}


def process_pre_tool_use(
    raw_payload: Union[str, bytes, Dict[str, Any]],
    policy_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Core authorization evaluation for PreToolUse events.
    Fails closed on any parse error, invalid input, policy error, or unauthorized tool.
    """
    # 1. Parse JSON input
    if isinstance(raw_payload, (str, bytes)):
        try:
            payload = json.loads(raw_payload)
        except Exception:
            return build_response("deny", "Malformed PreToolUse JSON payload")
    elif isinstance(raw_payload, dict):
        payload = raw_payload
    else:
        return build_response("deny", "Invalid PreToolUse payload type")

    if not isinstance(payload, dict):
        return build_response("deny", "PreToolUse payload must be a JSON object")

    # 2. Extract fields
    tool_name = (
        payload.get("toolName")
        or payload.get("tool_name")
        or payload.get("tool")
    )
    tool_input = (
        payload.get("toolInput")
        or payload.get("tool_input")
        or payload.get("input")
    )
    cwd_str = (
        payload.get("cwd")
        or payload.get("workingDirectory")
        or payload.get("repo_root")
    )

    if not tool_name or not isinstance(tool_name, str):
        return build_response("deny", "Missing or invalid toolName in PreToolUse payload")

    if tool_input is None or not isinstance(tool_input, dict):
        return build_response("deny", f"Missing or invalid toolInput for tool '{tool_name}'")

    # 3. Resolve repo root
    resolved_root: Path
    if repo_root is not None:
        resolved_root = Path(repo_root).resolve()
    elif cwd_str and isinstance(cwd_str, str):
        resolved_root = Path(cwd_str).resolve()
    else:
        resolved_root = HARNESS_ROOT.parent.resolve()

    # 4. Normalize tool invocation
    normalized = normalize_tool_invocation(tool_name, tool_input)
    if not normalized:
        return build_response(
            "deny",
            f"Tool '{tool_name}' is not authorized or invocation parameters are invalid",
        )

    # 5. Initialize AuthorizationEngine
    effective_policy_dir = policy_dir or (HARNESS_ROOT / "policies" / "trusted")
    try:
        engine = AuthorizationEngine.from_directory(effective_policy_dir)
    except ConfigurationError as ce:
        return build_response("deny", f"Authorization engine configuration error: {ce}")
    except Exception as ex:
        return build_response("deny", f"Authorization engine initialization failure: {type(ex).__name__}")

    # 6. Authorize invocation
    try:
        decision = engine.authorize(
            tool_name=normalized.harness_tool_name,
            invocation_input=normalized.invocation_input,
            repo_root=resolved_root,
        )
    except Exception as ex:
        return build_response("deny", f"Authorization error: {type(ex).__name__}")

    # 7. Map decision to Claude Code permissionDecision
    if decision == Decision.ALLOW:
        return build_response("allow")
    elif decision == Decision.REQUIRES_HUMAN_APPROVAL:
        return build_response("ask", "Action requires human approval per security policy")
    else:
        return build_response("deny", "Action denied by security policy")


def main() -> None:
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            result = build_response("deny", "Empty PreToolUse input")
        else:
            result = process_pre_tool_use(raw_input)
    except Exception as e:
        result = build_response("deny", f"Unexpected hook failure: {type(e).__name__}")

    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
