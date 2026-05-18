# Security Policy

## Supported Versions

This project is currently in early development. Security updates are
applied to the `main` branch. There are no formal releases yet.

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately.
**Do not open a public GitHub issue.**

To report a vulnerability:

1. Email the maintainer at [YOUR-REAL-EMAIL-HERE]
2. Include:
   - A description of the vulnerability
   - Steps to reproduce
   - Affected components (Agent API, frontend, ingestion, etc.)
   - Suggested mitigation if you have one

You should receive a response within 7 days acknowledging your report.

## Response Process

After acknowledgment, the maintainer will:

1. Reproduce and assess severity (within 14 days)
2. Develop a fix (timeline varies by severity)
3. Coordinate disclosure with you
4. Credit you in the security advisory unless you prefer anonymity

## Threat Model

See [THREAT_MODEL.md](THREAT_MODEL.md) for the scope of threats this
project considers. Reports that fall outside the documented threat
model are still welcome but may be marked as out-of-scope rather than
addressed with a fix.

## Known Limitations

Several risks are inherent to local-LLM applications and cannot be
fully mitigated:

- **Prompt injection** from documents, web content, or LLM outputs
- **LLM hallucinations** producing confidently-wrong information
- **Compromised local machine** — this system does not defend against
  attackers with shell access to the host

The threat model documents these explicitly.
