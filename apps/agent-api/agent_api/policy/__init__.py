"""Phase C policy layer: structured intents, resource sensitivity, and (Day 29+)
the pre-execution authorization engine. No tool executes a side effect without
first submitting an Intent here and receiving an allow decision."""


# Logged with every policy decision (see THREAT_MODEL.md T11). Bump this AND
# the doc when the Phase C threat-model assumptions change, so the audit log
# records which assumptions were in force for any past decision.
THREAT_MODEL_VERSION = "phase-c-v1"
