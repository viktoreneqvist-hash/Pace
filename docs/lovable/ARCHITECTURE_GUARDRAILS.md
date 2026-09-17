# Architecture guardrails

## Approved architecture

```text
Lovable-built React interface
        |
        | same-origin HTTP on localhost
        v
Pace FastAPI presentation/API adapter
        |
        v
existing Python services and validators
        |
        +--> SQLite / Alembic
        +--> Garmin integration
        +--> OpenAI clients
```

`uv run pace serve` remains the single application start command. In the final
integration, FastAPI serves both the built React assets and the local API.

## Why this boundary exists

The existing Python application is not a disposable backend prototype. It
contains the product's integrity:

- normalized Garmin ingestion and partial-failure handling;
- deterministic calculations and data-quality checks;
- explicit athlete preferences and context;
- AI fact selection and privacy minimization;
- immutable plan versions and target validation;
- confirmation, CSRF, and local security controls.

Recreating these rules in React, Supabase, or Lovable actions would create two
different Pace products and make safety regressions likely.

## Frontend rules

The frontend may:

- format normalized values;
- sort or filter already supplied presentation records;
- hold temporary form and dialogue state;
- render optimistic busy states without claiming completion;
- request explicit mutations and display their server result.

The frontend may not:

- calculate recovery baselines, continuity, eligibility, zones, or coaching
  conclusions;
- decide whether a plan is valid or active;
- call Garmin or OpenAI directly;
- read or write SQLite directly;
- store API keys, Garmin credentials, tokens, or private notes in browser
  persistence;
- silently retry expensive or provider-facing operations;
- turn a failed request into a success state;
- expose the application beyond loopback.

## Prototype repository strategy

Lovable creates and synchronizes its own GitHub repository and cannot import
the current Pace repository. Therefore:

1. Prototype in a separate `pace-ui` repository with synthetic fixtures.
2. Approve the information architecture and visual system there.
3. Integrate the exported source into `frontend/` in the main Pace repository.
4. Keep `pace-ui` as disposable design history or archive it after integration.
5. The main Pace repository remains the release and product source of truth.

## Security requirements for final integration

- Bind only to `127.0.0.1`.
- Preserve Trusted Host validation and restrictive CSP/security headers.
- Use same-origin requests and the existing local session.
- Require CSRF confirmation for persistent POST/PATCH/DELETE actions.
- Return normalized DTOs, never ORM rows or raw provider payloads.
- Keep secrets server-side and owner-only on disk.
- Disable browser caching for private application data.
- No remote fonts, analytics, error trackers, CDNs, or telemetry by default.

## Failure semantics

Every asynchronous operation needs explicit states:

```text
idle -> confirming -> running -> completed
                            \-> partial
                            \-> failed
                            \-> authentication required
                            \-> rate limited
```

The UI must not leave a button spinning indefinitely. Long 80-day syncs expose
batch progress, the completed range, partial results, and a safe retry action.
