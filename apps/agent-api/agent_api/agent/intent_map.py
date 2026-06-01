"""Bridge: canonical ToolCall -> Phase C Intent.

In D37 the local tools gate themselves internally, so the loop relies on that
and does NOT pre-gate. This module exists for D38+, where the loop needs to SEE
the gate decision (to pause for approval) BEFORE executing. It maps a model's
tool call to the Intent the policy engine evaluates. Kept minimal now; expanded
as approve-required tools are wired.
"""

from __future__ import annotations

from agent_api.agent.types import ToolCall
from agent_api.policy.intent import Intent, Tool, Action

# Map canonical tool names -> (Tool, Action). Read-only tools included now;
# write/commit/shell added in D38+.
_TOOL_ACTION = {
    "read_file":  (Tool.FILESYSTEM, Action.READ_FILE),
    "list_dir":   (Tool.FILESYSTEM, Action.LIST_DIR),
    "git_status": (Tool.GIT, Action.GIT_STATUS),
    "git_diff":   (Tool.GIT, Action.GIT_DIFF),
    "git_log":    (Tool.GIT, Action.GIT_LOG),
}


def map_tool_call_to_intent(call: ToolCall) -> Intent | None:
    """Best-effort map for loop-level gating (D38+). Returns None if the tool
    isn't a gated Phase C action (e.g. onboard, which composes gated reads)."""
    pair = _TOOL_ACTION.get(call.name)
    if pair is None:
        return None
    tool, action = pair
    resource = call.args.get("path")
    return Intent(tool=tool, action=action, resource=resource,
                  args=[str(v) for v in call.args.values()])
