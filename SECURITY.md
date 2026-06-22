# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in ForkReplay, please report it privately.

- **Email:** security@forkreplay.dev *(replace with your project's security contact)*
- Alternatively, open a [GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories)
  ("Report a vulnerability") on this repository.

Please do **not** open a public issue for security reports. We aim to acknowledge reports
within 3 business days and to provide a remediation timeline after triage. Coordinated
disclosure is appreciated; we will credit reporters who wish to be named.

## Supported versions

ForkReplay is pre-1.0. Security fixes are applied to the latest release on the default
branch. Pin to a released tag for production and watch the repository for advisories.

## Secrets policy for contributors

ForkReplay is a self-hostable, open-source project. **Never commit secrets or proprietary
identifiers** — credentials, API keys, JWTs, database passwords, cloud account IDs,
project refs, service endpoints, or personal/operator data — to this repository, including
in comments, fixtures, or example files.

- Real configuration belongs in your secret manager and in local, gitignored files
  (`.env.local`, `*.local.md`); see `.gitignore` and `.env.example`.
- Use `${PLACEHOLDER}` markers in committed templates (see
  `docs/operations/provisioning-template.md`).
- CI runs a secret scan (gitleaks) on pull requests; do not disable it to land a change.

If you accidentally commit a secret, treat it as compromised: **rotate it immediately**,
then remove it from the working tree. Rotation is required regardless of any history
rewrite, because committed values must be assumed exposed.

## Repository history

This repository's git history was reset prior to being made public, so it carries no
secret-bearing or identifying history from the project's private planning phase. The public
history begins from a single clean initial commit.
