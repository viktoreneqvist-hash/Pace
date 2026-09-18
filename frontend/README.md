# Pace frontend

This directory contains the editable React and TypeScript source for Pace's
local browser interface. The reviewed design originated in the separate
Lovable prototype recorded in `UPSTREAM.md`; this copy is now owned and built
by the main Pace repository.

Production uses `HttpPaceClient` and same-origin `/api/v1/*` requests to the
local FastAPI process. It does not use Lovable Cloud, Supabase, authentication,
telemetry, or a separate JavaScript server.

## Contributor workflow

```bash
npm install
npm run typecheck
npm run lint
npm run build
```

Copy the verified contents of `dist/` into
`src/pace/web/frontend_dist/` before building a Python release. End users do
not need Node.js; the static output ships inside the Pace package.

For isolated design work only, set `VITE_PACE_USE_MOCKS=true`. The default
build always reads real local Pace data through FastAPI.
