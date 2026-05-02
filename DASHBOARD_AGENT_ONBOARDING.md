# Dashboard Agent Onboarding

This document is for future coding agents working on the UTTDTY Dashboard, especially the Mission Control dashboard we added inside the existing Django app.

Use this as the handoff brief before enhancing, debugging, or adding features to the dashboard.

## Product Intent

Mission Control is a logged-in personal command center for the app database. It should feel like a calm, high-signal operational dashboard rather than a generic admin panel.

The main goal is to help the user see what needs attention across tasks and calendar data without using pgAdmin or writing SQL manually.

Visual direction:

- Dark navy / black background.
- Modular cards, panels, grids, and compact sections.
- Clean modern UI with a slightly technical mission-control feel.
- Status communicated through small badges, dots, pills, progress indicators, and alert-like labels.
- Accent colors in cyan, blue, green, amber, red, and violet.
- Polished and calm, not playful.
- Avoid a plain CRUD-admin look.

## Current Architecture

This is not a standalone Next.js app.

Mission Control lives inside the existing Django app and is only accessible after the user logs in through the existing Google OAuth flow.

High-level architecture:

```text
Browser
  -> Django authenticated route /mission-control/
  -> React/Vite frontend mounted in Django template
  -> same-origin Django JSON endpoints
  -> PostgreSQL via Django backend
```

Django owns:

- Authentication and session handling.
- CSRF protection.
- PostgreSQL access.
- Data safety and write restrictions.
- Serving the Mission Control HTML page.

React/Vite owns:

- The dashboard UI.
- Client-side screen switching.
- Task board interactions.
- Calls to Django JSON endpoints.

The browser must never receive database credentials.

## Important Files

Django route and API:

- `src/dashboard/urls.py`
- `src/dashboard/views.py`
- `src/dashboard/mission_control.py`
- `src/dashboard/templates/dashboard/mission_control.html`

React/Vite frontend:

- `frontend/mission-control/package.json`
- `frontend/mission-control/vite.config.ts`
- `frontend/mission-control/src/main.tsx`
- `frontend/mission-control/src/styles.css`

Generated static assets:

- `src/dashboard/static/dashboard/mission-control/app.js`
- `src/dashboard/static/dashboard/mission-control/app.css`

Configuration:

- `config/settings.py`
- `.env`
- `requirements.txt`
- `requirements.lock.txt`

Reference schema:

- `DATABASE_DATA_POINTS.md`

Deployment/run instructions:

- `README.md`

## Deployment Context

This project runs on a VPS for the public site `uttdty.com`.

The app is served by systemd using Uvicorn, roughly:

```ini
WorkingDirectory=/home/pmpmt/app/uttdty_dashboard
EnvironmentFile=/home/pmpmt/app/uttdty_dashboard/.env
ExecStart=/home/pmpmt/app/uttdty_dashboard/.venv/bin/uvicorn config.asgi:application --host 127.0.0.1 --port 8010
```

Assume there is a reverse proxy in front of Uvicorn for the public domain.

After frontend changes:

```bash
cd /home/pmpmt/app/uttdty_dashboard/frontend/mission-control
npm install
npm run build
```

Then collect static files:

```bash
cd /home/pmpmt/app/uttdty_dashboard
.venv/bin/python manage.py collectstatic --noinput
```

Then restart the service:

```bash
sudo systemctl restart uttdty-dashboard
```

The actual service name may differ. Check before restarting.

## Public Server Noise And Crawlers

This app is on the public internet, so logs may contain bot/scanner traffic.

Common examples:

```text
Invalid HTTP_HOST header: 'server.ip.address'
GET /robots.txt
GET /wiki
GET /accounts/login/
GET /accounts/google/login/
```

Interpretation:

- Direct-IP or unknown-host requests are usually scanners hitting the VPS by IP rather than `uttdty.com`.
- These should not be added to `ALLOWED_HOSTS` unless the user explicitly wants direct-IP access.
- The custom middleware catches invalid `Host` headers early and returns a quiet `400 Bad Request`.
- `/robots.txt` exists to reduce polite crawler noise and returns `Disallow: /`.
- `NoIndexMiddleware` adds `X-Robots-Tag: noindex, nofollow` so search engines should not index the login/dashboard pages.
- `robots.txt` and `X-Robots-Tag` only guide polite crawlers. They do not stop malicious scanners.

If future agents see crawler logs, do not assume the app is compromised. First check whether requests are being rejected with `400`, redirected to login, or blocked by normal authentication.

## Data Model Assumptions

Mission Control reads real PostgreSQL data from day one.

The Django settings now use `DATABASE_URL` from `.env` when present. PostgreSQL is the intended production database.

Current Phase 1 tables:

- `accounts_customuser`
- `managed_lists_todorecord`
- `managed_lists_todoitem`
- `calendar_parser_calendarevent`
- `batch_calendar_batchcalendarrequest`
- `batch_calendar_batchcalendarevent`

The schema reference in `DATABASE_DATA_POINTS.md` is important, but always verify the live database before adding queries.

## User Scope

Mission Control is a single-user personal dashboard.

The current backend selects the most plausible active personal user in `src/dashboard/mission_control.py`, preferring active non-superusers with task/calendar data.

Do not add a user selector unless explicitly requested.

If adding a feature that needs user scoping, preserve the current pattern:

- Resolve the selected user server-side.
- Filter all data by that user.
- Keep the helper isolated so a future user selector can be added without rewriting queries.

## Current Screens

### Tasks

The Tasks screen is a kanban-style board.

Columns:

- Backlog
- In Progress
- Done

Read mapping:

```text
open         -> Backlog
in_progress -> In Progress
on_hold      -> In Progress
done         -> Done
```

Write mapping:

```text
Backlog     -> open
In Progress -> in_progress
Done        -> done
```

Hidden by default:

```text
completion_status = cancelled
is_deleted = true
deleted_at is not null
```

Task cards should show useful available fields:

- `text`
- `description`
- `priority`
- `due_date`
- `due_time`
- `topic`
- `subtopic`
- `entity_name`
- `created_at`

### Calendar

The Calendar screen shows today and tomorrow.

It reads both calendar sources:

- `calendar_parser_calendarevent`
- `batch_calendar_batchcalendarevent`

Visually distinguish:

- `calendar_parser_calendarevent`: legacy / confirmed events.
- `batch_calendar_batchcalendarevent`: generated batch events with status such as pending, failed, skipped, or success.

Calendar is read-only in Phase 1.

## Write Safety Rules

Be conservative with database writes.

Allowed in Phase 1:

```text
Update managed_lists_todoitem.completion_status
```

Not allowed unless the user explicitly approves a new phase:

- Hard delete rows.
- Edit calendar events.
- Edit users.
- Edit billing.
- Edit OAuth secrets.
- Modify raw ingest records.
- Modify classification records.
- Modify retrieval embeddings.

Never display sensitive fields such as OAuth tokens or encrypted secrets. Ignore `accounts_usersecret` for UI purposes.

All writes must:

- Require login.
- Use CSRF protection.
- Validate the requested operation.
- Check task ownership through `managed_lists_todorecord`.
- Ignore deleted rows.
- Update only the intended field.

## Backend Guidance

Prefer keeping Mission Control backend logic in `src/dashboard/mission_control.py` unless a feature grows large enough to justify a new module.

Use Django views in `src/dashboard/views.py` for same-origin JSON endpoints.

Keep API responses shaped for the frontend, but do not move business rules into React.

When adding a new endpoint:

- Protect it with `@login_required`.
- Use `@require_GET`, `@require_POST`, or the appropriate method decorator.
- For writes, require CSRF and validate payloads strictly.
- When decoding JSON request bodies, handle both malformed JSON and invalid UTF-8. Catch `json.JSONDecodeError` and `UnicodeDecodeError`, and return a clean `400` response instead of allowing malformed input to become a server error.
- Return clear JSON errors with appropriate HTTP status codes.

Raw SQL is acceptable for dashboard read models because many referenced tables are existing database tables rather than Django models in this repo. Keep SQL readable and scoped.

## Frontend Guidance

Mission Control frontend lives under `frontend/mission-control`.

The Vite build outputs static files to:

```text
src/dashboard/static/dashboard/mission-control/
```

The Django template loads:

```text
dashboard/mission-control/app.css
dashboard/mission-control/app.js
```

When enhancing the UI:

- Keep the dark command-center visual style.
- Prefer dense but readable cards/panels.
- Use badges and compact metadata rather than large forms.
- Keep the first screen useful with real data.
- Avoid fake demo data unless the real query is empty, and label it clearly if used.
- Avoid adding authentication logic to React.

React should call same-origin Django endpoints using existing session cookies.

For POST requests, include the `csrftoken` cookie in the `X-CSRFToken` header.

## Development Workflow For Future Agents

Before changing code:

1. Read this document.
2. Read `README.md`.
3. Inspect `src/dashboard/mission_control.py`, `src/dashboard/views.py`, and `frontend/mission-control/src/main.tsx`.
4. Check `DATABASE_DATA_POINTS.md` for schema intent.
5. Verify live table/column details before writing new queries.

During implementation:

1. Keep Django auth unchanged unless explicitly asked.
2. Keep database access server-side.
3. Keep frontend changes in `frontend/mission-control`.
4. Build assets with `npm run build`.
5. Run Django checks.
6. Run frontend type checks.
7. Test JSON endpoints and any write path.

Recommended checks:

```bash
cd /home/pmpmt/app/uttdty_dashboard
.venv/bin/python manage.py check
```

```bash
cd /home/pmpmt/app/uttdty_dashboard/frontend/mission-control
npm run lint
npm run build
```

After deployment-facing frontend changes:

```bash
cd /home/pmpmt/app/uttdty_dashboard
.venv/bin/python manage.py collectstatic --noinput
```

## When To Ask The User

Ask before:

- Adding new write operations.
- Changing the Google login flow.
- Changing deployment/service configuration.
- Exposing more personal data in the UI.
- Adding a user selector.
- Adding calendar editing.
- Changing the public URL structure.
- Introducing a major new framework or package.

Do not ask for trivial visual choices if the existing style provides enough direction.

## Current Phase Boundary

Phase 1 is complete when:

- `/mission-control/` loads only after login.
- Tasks are read from PostgreSQL.
- Calendar events are read from PostgreSQL.
- Task movement updates only `managed_lists_todoitem.completion_status`.
- Frontend assets build successfully.
- Django checks pass.

Phase 2 should only start after Phase 1 is working and the user gives feedback.
