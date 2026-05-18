# Contributing

Thanks for considering a contribution. This document describes how to
participate, what's in scope, and the legal framework for contributions.

## Project status

This project is currently developed primarily by one maintainer. The
roadmap is in active flux. Before opening a large PR, please open an
issue to discuss the change first.

## Developer Certificate of Origin (DCO)

This project uses the [Developer Certificate of Origin](https://developercertificate.org/)
for contributions. By signing your commits with `git commit -s`, you
certify the contents of the DCO.

In practice: run `git commit -s` (or `git commit --signoff`) to add a
`Signed-off-by:` line to your commit message. That's it.

## How to contribute

### Bug reports

Open a GitHub issue with:

- A clear title describing the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, hardware)
- Any relevant logs (with sensitive data redacted)

### Feature requests

Open a GitHub issue describing:

- The use case you're trying to solve
- Why existing functionality doesn't meet the need
- A rough sketch of how the feature might work

Roadmap items are tracked in `docs/`. Feature requests that align with
the existing roadmap will get faster responses than those that don't.

### Code contributions

Workflow:

1. Open an issue first for non-trivial changes
2. Fork the repository
3. Create a feature branch (`git checkout -b feature/your-feature`)
4. Make your changes
5. Run the eval harness if you changed retrieval, chunking, or model code
6. Sign off your commits with `git commit -s`
7. Open a pull request against `main`

### What's in scope

- Bug fixes
- Improvements to retrieval quality, model integration, UI
- Documentation improvements
- New language support for code highlighting
- Eval question additions
- Reusable prompts and templates

### What's not in scope (currently)

- Multi-tenant or hosted-service features
- Cloud deployment scripts (planned for post-features)
- Major UI redesigns
- Breaking changes to the API contract

If you're unsure whether your idea is in scope, please open an issue
first.

## Code style

- Python: follow PEP 8
- JavaScript/HTML/CSS: match the existing style. No build step, no
  framework.
- Markdown: follow CommonMark.

## License

By contributing, you agree your contributions will be licensed under
the Apache License 2.0, the same license as the project.
