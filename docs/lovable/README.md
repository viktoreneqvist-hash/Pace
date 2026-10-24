# Pace + Lovable handoff

This folder is the design handoff for rebuilding Pace's interface in Lovable
without replacing the existing product core.

## What Lovable is responsible for

Lovable may create:

- the React user interface;
- navigation, layout, responsive behaviour, and visual hierarchy;
- charts and structured workout presentation;
- loading, empty, success, and error states;
- mock interactions over synthetic data.

Lovable is not responsible for:

- Garmin authentication or synchronization;
- OpenAI requests or prompt contracts;
- training calculations, rules, or plan validation;
- SQLite, Alembic, repositories, or durable application state;
- security decisions or secret storage.

Those capabilities already exist in Pace's Python application and remain the
system of record.

## Files in this package

- `PROJECT_KNOWLEDGE.md` — compact text for Lovable Project Knowledge.
- `PRODUCT_BRIEF.md` — product, user, and value proposition.
- `ARCHITECTURE_GUARDRAILS.md` — boundaries the prototype must not cross.
- `DESIGN_DIRECTION.md` — visual and interaction direction.
- `SCREEN_SPECIFICATIONS.md` — required screens and important states.
- `DATA_CONTRACTS.md` — proposed frontend/backend boundary.
- `LOVABLE_MASTER_PROMPT.md` — the first prompt to paste into Lovable.

The existing screenshots in `docs/assets/` are factual references for content
density and product scope. They are not a visual style that must be copied.

## Exact first prototype workflow

1. Create a new blank Lovable project named **Pace UI Prototype**.
2. Do not enable Lovable Cloud, Supabase, authentication, or external APIs.
3. Open Project settings and paste all of `PROJECT_KNOWLEDGE.md` into Project
   Knowledge.
4. Upload the three screenshots from `docs/assets/` as content references.
5. Open Lovable Plan mode and paste `LOVABLE_MASTER_PROMPT.md`.
6. Ask Lovable to produce a plan before it changes code.
7. Build the application with synthetic mock data only.
8. Review the desktop and mobile layouts before connecting GitHub.
9. Connect the Lovable project to a new repository named `pace-ui`. Lovable
   cannot import the existing Pace repository, so do not point it at the main
   repository.
10. After the UI is approved, export or copy the frontend into `frontend/` in
    the Pace repository and replace its mock adapter with the local Pace API.

## Definition of a successful prototype

The prototype is successful when a new user can understand today's decision,
the active plan, recent training and recovery, upcoming races, and required
actions without reading JSON or using a terminal. It does not need live Garmin,
OpenAI, or SQLite access at this stage.
