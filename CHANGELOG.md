# Changelog

Notable user-visible changes to Pace are recorded here.

## Unreleased

### Added

- Separate seven-day Garmin activity-detail sync with normalized aggregate
  heart-rate time in zones on the dashboard and session detail page
- Explicit, per-session Garmin workout export with calendar scheduling,
  optional device push, and duplicate-safe local mappings

### Changed

- Upgraded `garminconnect` from 0.3.6 to 0.3.16 with the typed workout extra

## 0.1.0-alpha.1 — 2026-09-16

First public alpha of Pace's Garmin-first, local coaching loop.

### Added

- Guided browser onboarding and settings
- Bounded Garmin history and recovery sync
- Deterministic training, recovery, data-quality, and trend facts
- Race-aware and general 14-day plans with structured sessions
- Coach dialogue with confirmable feedback and context actions
- Dashboard, active plan, weekly review, and synthetic product demo
- Public-alpha README, contribution guide, security policy, and GitHub templates
- Host-header validation and restrictive browser security headers for the local UI
- Package metadata and a single installed source for the displayed version

### Changed

- Vision, architecture, decision summary, roadmap, and contributor guidance now
  describe the current local web and AI coaching system
- The v0.1 interface and generated coach output use English
- The package version is represented as the PEP 440 prerelease `0.1.0a1`

### Security

- Full Git history scanned with Gitleaks before publication; no leaks found
- GitHub Dependabot vulnerability alerts enabled
- GitHub secret scanning, push protection, automated security fixes, and
  private vulnerability reporting enabled

### Known limitations

- Garmin Connect access is unofficial and can break when Garmin changes its
  private service.
- The alpha.1 tag used `garminconnect==0.3.6`; the unreleased branch now uses
  0.3.16 and still requires a real Garmin smoke test before the next tag.
- macOS and Python 3.14 are the currently tested platform and runtime.
- Pace is local, single-athlete alpha software, not medical care or a hosted
  service.
