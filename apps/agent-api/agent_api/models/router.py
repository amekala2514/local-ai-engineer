"""Model routing logic.

Two responsibilities:
1. pick_model(task_type) - manual selection by task type string
2. auto_route(message) - inspect the message and decide which model fits

Auto-routing uses keyword heuristics. Transparent, fast, debuggable. We
return a (model, reason) tuple so the UI can show why a given model was
chosen. If this proves insufficient, we can upgrade to LLM-as-classifier
later without changing the call sites.
"""

import re
from dataclasses import dataclass

from agent_api.settings import settings


TASK_TYPES = {"general", "code", "code_heavy", "auto"}


@dataclass
class RoutingDecision:
    """Result of routing logic."""

    task_type: str  # "general", "code", or "code_heavy" (never "auto")
    model: str
    reason: str


# Keywords that suggest a coding task
_CODE_KEYWORDS = re.compile(
    r"\b("
    r"function|class|method|variable|import|export|return|"
    r"def |async |await |yield |lambda|"
    r"git|commit|branch|merge|rebase|diff|"
    r"python|javascript|typescript|java|kotlin|swift|go(?:lang)?|rust|"
    r"ruby|php|scala|c\+\+|csharp|"
    r"docker|kubernetes|k8s|terraform|ansible|"
    r"sql|postgres|mysql|sqlite|redis|mongo|"
    r"api|endpoint|request|response|http|json|yaml|xml|"
    r"bug|error|exception|traceback|stack ?trace|stacktrace|"
    r"test|pytest|unittest|jest|mocha|"
    r"refactor|optimize|debug|fix"
    r")\b",
    re.IGNORECASE,
)

# Code-shaped signals: triple backticks, file paths, specific punctuation
_HAS_CODE_FENCE = re.compile(r"```")
_HAS_FILE_PATH = re.compile(r"\b[\w/-]+\.(py|js|ts|tsx|jsx|java|kt|go|rs|rb|php|cpp|c|h|hpp|cs|swift|sql|yaml|yml|json|toml|md|sh|bash)\b")
_HAS_TRACEBACK = re.compile(r"(File \".+?\", line \d+|at \w+\.<\w+>|Traceback \(most recent)", re.IGNORECASE)

# Signals for hard / multi-file code work that warrants the heavy model
_HEAVY_KEYWORDS = re.compile(
    r"\b("
    r"refactor|architecture|design|multi[- ]?file|"
    r"explain.*(?:codebase|repository|repo)|"
    r"review.*(?:pull request|pr|diff)|"
    r"performance|optimization|profiling|"
    r"concurrent|concurrency|race condition|deadlock|"
    r"algorithm complexity|big[- ]?o"
    r")\b",
    re.IGNORECASE,
)


def auto_route(message: str) -> RoutingDecision:
    """Decide which model to use based on the message content."""
    # Trim very short messages - they're usually greetings/follow-ups
    msg = (message or "").strip()
    if len(msg) < 8:
        return RoutingDecision(
            task_type="general",
            model=settings.model_general,
            reason="short message, defaulting to general",
        )

    # Strong code signals: code fences, tracebacks, file paths
    if _HAS_CODE_FENCE.search(msg):
        if _HEAVY_KEYWORDS.search(msg):
            return RoutingDecision(
                task_type="code_heavy",
                model=settings.model_code_heavy,
                reason="contains code fence + complex-reasoning keywords",
            )
        return RoutingDecision(
            task_type="code",
            model=settings.model_code,
            reason="contains code fence",
        )

    if _HAS_TRACEBACK.search(msg):
        return RoutingDecision(
            task_type="code",
            model=settings.model_code,
            reason="contains a stack trace",
        )

    if _HAS_FILE_PATH.search(msg):
        if _HEAVY_KEYWORDS.search(msg):
            return RoutingDecision(
                task_type="code_heavy",
                model=settings.model_code_heavy,
                reason="references a file + complex-reasoning keywords",
            )
        return RoutingDecision(
            task_type="code",
            model=settings.model_code,
            reason="references a code file",
        )

    # Weaker code signal: matched keywords
    if _CODE_KEYWORDS.search(msg):
        if _HEAVY_KEYWORDS.search(msg):
            return RoutingDecision(
                task_type="code_heavy",
                model=settings.model_code_heavy,
                reason="code keywords + complex-reasoning keywords",
            )
        return RoutingDecision(
            task_type="code",
            model=settings.model_code,
            reason="contains code-related keywords",
        )

    # Heavy without code is unusual but possible (deep architectural discussion)
    if _HEAVY_KEYWORDS.search(msg):
        return RoutingDecision(
            task_type="general",
            model=settings.model_general,
            reason="complex-reasoning keywords but no code signal; using general",
        )

    return RoutingDecision(
        task_type="general",
        model=settings.model_general,
        reason="no code signals detected",
    )


def pick_model(task_type: str, message: str = "") -> RoutingDecision:
    """Return a RoutingDecision for the given task type.

    For task_type='auto', uses auto_route(). Otherwise maps directly.
    """
    if task_type == "auto":
        return auto_route(message)
    if task_type == "code":
        return RoutingDecision(
            task_type="code",
            model=settings.model_code,
            reason="user selected code model",
        )
    if task_type == "code_heavy":
        return RoutingDecision(
            task_type="code_heavy",
            model=settings.model_code_heavy,
            reason="user selected code-heavy model",
        )
    return RoutingDecision(
        task_type="general",
        model=settings.model_general,
        reason="user selected general model",
    )
