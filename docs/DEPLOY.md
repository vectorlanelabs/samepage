# Deploying Same Page

Same Page is a single FastAPI app on SQLite, fronted by Caddy for HTTPS. One
VPS, two containers (`app` + `caddy`), one persistent volume for the database.
Alembic migrations run automatically at app startup — there is no separate
migrate step. The production database starts **empty**; there is no seed data.

> **Status:** these artifacts are ready for the *first* deploy. The GitHub
> Actions pipeline is intentionally NOT in the repo yet — CI stays off until
> Charlie provides the domain and gives the go-ahead (CLAUDE.md #10). Until
> then, deploy by hand with the steps below.

## Prerequisites

1. A VPS with Docker + Docker Compose, ports 80 and 443 free.
2. A domain pointed (A/AAAA record) at the VPS.
3. A Google OAuth client (see `REQUESTS.md` for the console walkthrough): its
   client id + secret, with `https://<your-domain>/auth/google/callback` added
   as an authorized redirect URI.

## One-time setup

Create a `.env` next to `docker-compose.yml` (never commit it):

```
SP_DOMAIN=samepage.example.com
SP_SECRET=<openssl rand -hex 32>
SP_GOOGLE_CLIENT_ID=<from Google Cloud Console>
SP_GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
```

`SP_SECRET` signs the session cookies — keep it stable (rotating it logs
everyone out) and secret. The app reads `SP_ENV=production` (set in the image),
which turns on the `Secure` cookie flag; it only works over real HTTPS, which
Caddy provides.

## Deploy

```bash
docker compose up -d --build
```

Caddy fetches a Let's Encrypt certificate on first boot (needs DNS already
pointing at the box and ports 80/443 reachable). Watch the first startup:

```bash
docker compose logs -f app     # migrations run here; a migration failure aborts boot by design
docker compose logs -f caddy   # certificate issuance
```

Then visit `https://<your-domain>` — sign in with Google, create a group, and
create a collection. There is no seed data; the library starts empty and is
built in-app.

## Reverse-proxy gotcha (already handled, don't undo)

The app's CSRF protection compares the request `Origin` against the `Host`
header verbatim. Caddy's `reverse_proxy` forwards the original Host by default,
so the provided `Caddyfile` works as-is. If you swap in a different proxy, it
**must** forward the original Host (nginx: `proxy_set_header Host $host;`) or
every form submission will 403.

## Backups

The whole durable state is one SQLite file (plus its WAL sidecars) on the
`samepage-data` volume. Back it up WAL-safely — never `cp` a live WAL database:

```bash
# from the host, using sqlite3 against the mounted volume (recommended):
sqlite3 /var/lib/docker/volumes/samepage_samepage-data/_data/samepage.db \
  ".backup '/path/to/backups/samepage-$(date -u +%Y%m%dT%H%M%SZ).db'"
# or run the bundled script (it lives in the repo, not the slim image — run it
# from a checkout with sqlite3 installed, pointed at the volume path above):
deploy/backup.sh <db-path> <backup-dir>
```

`deploy/backup.sh` uses `sqlite3 .backup`, integrity-checks the snapshot, and
prunes backups older than `RETENTION_DAYS` (default 14). Schedule it from cron
(e.g. `17 3 * * *`). Periodically prove the backups restore:

```bash
docker compose exec app deploy/restore-check.sh /data/backups
```

`restore-check.sh` restores the newest backup into a scratch copy and asserts
it's at Alembic head with the core tables queryable — a backup you've never
restored is a hope, not a backup.

## Upgrades

```bash
git pull
docker compose up -d --build     # migrations run at startup; take a backup first
```

Take a backup before upgrading. Migrations are forward-only in practice; the
downgrade paths exist but restoring a backup is the real rollback.
