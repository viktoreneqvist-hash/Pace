# Release validation — v0.1.0-alpha.1

Date: 2026-09-16

This record contains no athlete data, credentials, Garmin payloads, API keys,
or machine identifiers.

## External installation result

The maintainer reported a successful clean-clone test on a second Mac. The
following user journey completed without an observed error:

1. clone the public repository;
2. install dependencies with `uv sync`;
3. launch the local web application;
4. complete browser onboarding;
5. save the local OpenAI configuration;
6. authenticate with Garmin and complete the standard history sync;
7. save coaching preferences and create the first plan.

Together with the isolated clean-install check and normal validation on the
development Mac, this satisfies the two-Mac alpha gate. It does not claim
support for every macOS version, processor, Garmin account, or MFA flow.

## Garmin client decision

The live-tested `garminconnect==0.3.6` dependency remains pinned for this
release. Version 0.3.15 was identified as available but was not substituted
after the successful live test. Its evaluation is intentionally deferred to a
separate compatibility change that requires another live, read-only check.

## Automated release gate

- Ruff passes.
- The synthetic test suite passes without Garmin or OpenAI access.
- A blank SQLite database migrates to the single Alembic head.
- CLI and loopback-web smoke tests pass.
- Dependency, static-security, and full-history secret scans have no
  unexplained high-risk finding.
- GitHub vulnerability alerts, automated security fixes, secret scanning, push
  protection, and private vulnerability reporting are enabled.
- README behavior and known limitations match the shipped alpha.
