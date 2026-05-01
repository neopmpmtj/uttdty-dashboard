# UTTDTY Dashboard

Django/Uvicorn dashboard for `uttdty.com` with Google login and the Mission Control interface for personal task and calendar data.

## VPS First Run / Deploy

These instructions assume the app lives at:

```text
/home/pmpmt/app/uttdty_dashboard
```

and is run by systemd with Uvicorn on:

```text
127.0.0.1:8010
```

### 1. Create or refresh the Python virtual environment

```bash
cd /home/pmpmt/app/uttdty_dashboard
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Check the server environment file

The systemd service uses:

```text
/home/pmpmt/app/uttdty_dashboard/.env
```

Required for Mission Control:

```env
DATABASE_URL=postgresql://appuser:...@localhost:5432/voicediary_db
```

Do not commit `.env`.

For the public site, `.env` should also include the production host/security values already used by the app, such as:

```env
ALLOWED_HOSTS=uttdty.com,www.uttdty.com,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://uttdty.com,https://www.uttdty.com
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
```

### 3. Install and build Mission Control frontend assets

```bash
cd frontend/mission-control
npm install
npm run build
```

The build writes Django-served static assets to:

```text
src/dashboard/static/dashboard/mission-control/
```

### 4. Collect Django static files

Run this after building the React/Vite assets:

```bash
cd /home/pmpmt/app/uttdty_dashboard
.venv/bin/python manage.py collectstatic --noinput
```

This copies the Mission Control assets into:

```text
staticfiles/
```

Your reverse proxy should serve `/static/` from that directory, or otherwise forward static requests to a static-file handler.

### 5. Run Django checks

```bash
cd /home/pmpmt/app/uttdty_dashboard
.venv/bin/python manage.py check
```

### 6. Install or verify the systemd service

The app is expected to run with a service like:

```ini
[Unit]
Description=UTTDTY Dashboard Django/Uvicorn App
After=network.target

[Service]
User=pmpmt
Group=pmpmt
WorkingDirectory=/home/pmpmt/app/uttdty_dashboard
EnvironmentFile=/home/pmpmt/app/uttdty_dashboard/.env
ExecStart=/home/pmpmt/app/uttdty_dashboard/.venv/bin/uvicorn config.asgi:application --host 127.0.0.1 --port 8010
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

After creating or changing the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable uttdty-dashboard
sudo systemctl restart uttdty-dashboard
sudo systemctl status uttdty-dashboard
```

Replace `uttdty-dashboard` with the actual service name if it differs.

### 7. Open Mission Control

Go to the public site, log in through the existing Google login flow, then visit:

```text
https://uttdty.com/mission-control/
```

## Useful Commands

Rebuild the Mission Control frontend after UI changes:

```bash
cd frontend/mission-control
npm run build
```

Type-check the frontend:

```bash
cd frontend/mission-control
npm run lint
```

Run Django checks:

```bash
cd /home/pmpmt/app/uttdty_dashboard
.venv/bin/python manage.py check
```

Collect static files after a frontend build:

```bash
cd /home/pmpmt/app/uttdty_dashboard
.venv/bin/python manage.py collectstatic --noinput
```

Restart the deployed app:

```bash
sudo systemctl restart uttdty-dashboard
```

Watch service logs:

```bash
sudo journalctl -u uttdty-dashboard -f
```

Run a local development server instead of systemd:

```bash
cd /home/pmpmt/app/uttdty_dashboard
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

## Notes

- Django owns authentication, database access, and write safety.
- Mission Control is available only after login at `/mission-control/`.
- The React frontend calls same-origin Django JSON endpoints.
- Phase 1 allows only one write operation: updating `managed_lists_todoitem.completion_status`.
- Calendar data is read-only in Phase 1.
- On the VPS, rebuild frontend assets and run `collectstatic` before restarting the systemd service.
