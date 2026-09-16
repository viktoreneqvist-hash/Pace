# Pace S1 Security Review

Review date: 2026-09-15

Baseline reviewed: `8c945ae` (`release: prepare Pace public alpha`)

## Outcome

Pace is suitable for its documented public-alpha deployment model: one athlete,
one local installation, and an HTTP server bound only to loopback. No P0 or P1
finding remains. The bounded P2 and P3 findings found during S1 were fixed and
covered by tests.

This conclusion does **not** approve internet hosting, shared computers,
multi-user use, or handling another athlete's data as a service. Those models
need authentication, authorization, encryption and retention work that Pace
deliberately does not contain.

## Threat model

### Assets

- Garmin email/password during the login request;
- reusable Garmin session tokens;
- OpenAI API key;
- local SQLite athlete data and structured context;
- plans, feedback, AI snapshots, and generated reports.

### Trust boundaries

1. The operating-system account protects local files and processes.
2. The browser talks only to `127.0.0.1` or `localhost`.
3. Garmin receives credentials and provider requests only during an explicit
   Garmin operation.
4. OpenAI receives selected normalized Pace facts only during an explicit AI
   operation; it does not receive credentials, tokens, raw Garmin payloads, or
   the database.
5. Git and GitHub may contain source and synthetic fixtures, never local athlete
   artifacts.

### Relevant attackers and failures

- a hostile website trying to reach a service on localhost;
- HTML or script injection through stored athlete/model text;
- accidental credential, token, database, or report publication;
- a vulnerable Python dependency;
- overly broad local file permissions;
- provider errors leaking credentials into the UI or logs;
- an accidental network bind beyond loopback.

An attacker who already controls the athlete's operating-system account is
outside the v0.1 boundary. Pace does not encrypt data against that same user or
against a compromised computer.

## Findings and resolution

| Severity | Finding | Resolution |
| --- | --- | --- |
| P2 | The main page and JSON API did not consistently prevent browser caching of private training data. | Every non-static web response now sends `Cache-Control: no-store`. |
| P2 | Parent directories created automatically for the default Garmin token path could inherit ordinary directory permissions even though the token directory and file were private. | Every directory Pace creates for the token path is set to `0700`; the existing `.local` directory was corrected without reading its contents. |
| P3 | State-changing endpoints had a strong CSRF token and no CORS permission, but did not independently reject a mismatched `Origin`. | Writes now reject a supplied foreign Origin before checking CSRF. Tests also confirm that hostile CORS preflight receives no permission. |
| P3 | Browser secret fields were not explicitly size-bounded, and a multiline OpenAI key could be written to the local environment file. | API key, password, and MFA inputs are bounded; saved API keys must be a single line. |
| P3 | The generic cookie name could collide with an unrelated localhost application. | The signed, HttpOnly, SameSite=Lax cookie is now named `pace_session`. |
| P3 | Three production assertions would disappear under Python optimized mode. | They are now explicit runtime integrity checks. |

## Controls verified

- Uvicorn listens on `127.0.0.1`, not `0.0.0.0`.
- Untrusted Host headers return HTTP 400.
- Missing or invalid CSRF confirmation returns HTTP 403.
- A foreign Origin is rejected even when a valid test CSRF token is supplied.
- Hostile CORS preflight is not granted an allowed origin.
- CSP, frame denial, no-sniff, referrer, resource, permissions, and no-store
  headers are present on live responses.
- Dynamic coach, plan, report, and settings content uses HTML escaping or safe
  text insertion. Embedded JSON replaces `<` before entering the document.
- The command box is an allowlist and cannot execute shell commands.
- Report access uses a fixed filename catalog plus resolved-parent validation.
- OpenAI provider errors are converted to bounded user-facing messages.
- Local secret/token files are `0600`; local sensitive directories are `0700`.
- Sensitive local paths are ignored and absent from tracked files.
- Gitleaks 8.30.1 scanned all 80 Git commits with full redaction and found no
  leak.
- `pip-audit` found no known vulnerability in the locked production dependency
  set.
- Bandit completed without a reportable source-code finding after the S1
  hardening changes.

## Validation

- Ruff: passed.
- Pytest: 247 passed.
- Alembic: a blank SQLite database upgraded to the single head
  `0a1b2c3d4e5f`.
- CLI: `pace 0.1.0` and help smoke checks passed.
- Live localhost probes: loopback bind, Host rejection, CSRF rejection, absent
  CORS permission, and security headers passed.
- `git diff --check`: passed after the S1 changes.

No Garmin login, Garmin synchronization, OpenAI request, token-content read, or
API-key-content read was performed during S1.

## Accepted limitations

- Pace has no application login because it is a single-user loopback program.
- Local data is not encrypted against the logged-in operating-system user.
- Legacy standalone reports need inline CSS and tooltip JavaScript; their
  generated values are escaped and the normal in-app pages retain a stricter
  policy.
- Long external Garmin/OpenAI operations can occupy a local request. This is an
  availability concern, not a remote exposure in the documented deployment.
- GitHub Actions use versioned action tags rather than commit SHAs and run with
  read-only repository contents. Full SHA pinning is optional supply-chain
  hardening for a later release.

## Release implication

S1 removes security review as a blocker for publishing the source. The remaining
release work is product/demo evidence, external clean-install testing, GitHub
feature availability, the owner's visibility decision, and the first release
tag. Any hosted or paid version requires a new security review and architecture.
