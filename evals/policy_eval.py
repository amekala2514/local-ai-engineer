"""Mock-intent suite for the policy engine. Proves allow/approve/deny decisions
BEFORE any real tool plugs in. Run: python -m evals.policy_eval"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "agent-api"))

from agent_api.policy.intent import Intent, Tool, Action, Scope, Reversibility
from agent_api.policy.engine import evaluate, Decision

# (name, intent, expected_decision)
CASES = [
    ("read source file",        Intent(tool=Tool.FILESYSTEM, action=Action.READ_FILE, resource="apps/agent-api/agent_api/main.py"), Decision.ALLOW),
    ("list a directory",        Intent(tool=Tool.FILESYSTEM, action=Action.LIST_DIR, resource="apps/agent-api"), Decision.ALLOW),
    ("git status",              Intent(tool=Tool.GIT, action=Action.GIT_STATUS), Decision.ALLOW),
    ("write a normal file",     Intent(tool=Tool.FILESYSTEM, action=Action.WRITE_FILE, resource="apps/agent-api/agent_api/foo.py", reversibility=Reversibility.PATCH_BACKUP), Decision.APPROVE),
    ("git commit",              Intent(tool=Tool.GIT, action=Action.GIT_COMMIT, reversibility=Reversibility.TEMP_BRANCH), Decision.APPROVE),
    ("run pytest",              Intent(tool=Tool.SHELL, action=Action.RUN_COMMAND, args=["pytest", "tests/"]), Decision.APPROVE),
    ("write .env (secret)",     Intent(tool=Tool.FILESYSTEM, action=Action.WRITE_FILE, resource=".env"), Decision.DENY),
    ("write ssh key",           Intent(tool=Tool.FILESYSTEM, action=Action.WRITE_FILE, resource="home/.ssh/id_rsa"), Decision.DENY),
    ("write CI workflow",       Intent(tool=Tool.FILESYSTEM, action=Action.WRITE_FILE, resource=".github/workflows/deploy.yml"), Decision.DENY),
    ("write outside repo",      Intent(tool=Tool.FILESYSTEM, action=Action.WRITE_FILE, resource="../../etc/passwd"), Decision.DENY),
    ("rm -rf",                  Intent(tool=Tool.SHELL, action=Action.RUN_COMMAND, args=["rm", "-rf", "build/"]), Decision.DENY),
    ("git force push",          Intent(tool=Tool.GIT, action=Action.GIT_PUSH, args=["--force"], resource="origin/main"), Decision.DENY),
    ("git normal push",         Intent(tool=Tool.GIT, action=Action.GIT_PUSH, resource="origin/main"), Decision.DENY),
    ("chained command",         Intent(tool=Tool.SHELL, action=Action.RUN_COMMAND, args=["ls", ";", "rm", "build/"]), Decision.DENY),
    ("read .env (secret)",      Intent(tool=Tool.FILESYSTEM, action=Action.READ_FILE, resource=".env"), Decision.DENY),
]

def main() -> int:
    passed = failed = 0
    print(f"{'case':24} {'expected':9} {'got':9} result")
    print("-" * 60)
    for name, intent, expected in CASES:
        res = evaluate(intent)
        ok = res.decision == expected
        passed += ok; failed += (not ok)
        mark = "PASS" if ok else "**FAIL**"
        print(f"{name:24} {expected.value:9} {res.decision.value:9} {mark}")
        if not ok:
            print(f"    reasons: {res.reasons}, signals: {[s.value for s in res.risk_signals]}")
    print("-" * 60)
    print(f"{passed}/{len(CASES)} passed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
