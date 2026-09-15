# Security Policy

## Supported version

Pace is pre-release software. Security fixes are applied to the latest commit
on `main`; older snapshots are not supported.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose Garmin
sessions, OpenAI keys, athlete data, or local files. Use GitHub's private
security advisory flow for this repository instead:

1. Open the repository's **Security** tab.
2. Choose **Advisories**.
3. Choose **Report a vulnerability**.

Include the affected version, reproduction steps, impact, and a suggested fix
when available. Do not include real credentials or another person's training
data.

## Security model

Pace is designed as a loopback-only, single-athlete application. It is not a
multi-user web service and must not be exposed directly to a public network.

Sensitive local files include:

- `.local/` — Garmin session tokens and local secrets;
- `data/` — the SQLite database and sidecar files;
- `reports/` — generated reports that may contain personal training data.

These paths are ignored by Git. Pace also restricts accepted web hosts and
adds browser security headers. Those protections do not turn it into an
internet-facing service.

Garmin integration is unofficial. Garmin credentials are used for login but
the password is not stored by Pace. OpenAI requests receive selected,
normalized Pace facts; raw Garmin payloads, tokens, credentials, and database
dumps are excluded.
