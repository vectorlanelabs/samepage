# Deploying Same Page

Same Page is a single FastAPI app on SQLite. Alembic migrations run
automatically at app startup — there is no separate migrate step. The
production database starts **empty**; there is no seed data.

## How it's deployed (production)

Production runs on a VPS via **Coolify** (Compose build strategy), deploying the
`samepage` app from `vectorlanelabs/samepage` `main`. Coolify provides the TLS
front door / reverse proxy internally, so the Compose file exposes the app on
port 8000 to Coolify's proxy only — **no host port mapping, no bundled Caddy**.
Production URL: `https://samepage.vectorlane.dev`.

The container: `Dockerfile` builds with `uv sync --frozen --no-dev`, runs as a
non-root user, drops privileges in `docker-entrypoint.sh`, and starts
`uvicorn app.main:app --proxy-headers`. The SQLite DB lives on the
`samepage-data` volume at `/data/samepage.db`; the root filesystem is read-only
(`/data` and `/tmp` are the only writable paths).

To ship a change: land it on `main`. A deploy is currently triggered **manually
in Coolify** (redeploy the `samepage` app); the CI pipeline to auto-trigger it
on `main` is not built yet (CLAUDE.md #10 — pending Charlie's go-word).

## Environment variables (set in Coolify, never in Git)

| Var | Required | Value |
|---|---|---|
| `SP_ENV` | yes | `production` (also set in the image) — enables Secure session cookies |
| `SP_SECRET` | yes | long random hex (`openssl rand -hex 32`); stable — rotating it logs everyone out |
| `SP_DB_PATH` | yes | `/data/samepage.db` (set in Compose) |
| `SP_BASE_URL` | **yes** | `https://samepage.vectorlane.dev` — the app builds the Google OAuth redirect URI from this; if unset it defaults to localhost and sign-in breaks |
| `SP_GOOGLE_CLIENT_ID` | yes | from Google Cloud Console (project `samepage`) |
| `SP_GOOGLE_CLIENT_SECRET` | yes | from Google Cloud Console |

No `SP_API_KEY` is used (M6a uses per-group tokens stored in the DB, not an env
var). The Google OAuth client's authorized redirect URI must be
`https://samepage.vectorlane.dev/auth/google/callback`.

## First-boot notes

- Migrations run at startup and a migration failure aborts boot by design —
  watch the container logs on first deploy.
- The DB starts empty: sign in with Google, create a group, create a collection,
  add items in-app. If a previous (skeleton) deploy left data on the volume and
  you want a truly clean start, reset the `samepage-data` volume before deploying.

## Backups

The durable state is one SQLite file (+ WAL sidecars) on `samepage-data`. Back
it up WAL-safely — never `cp` a live WAL database:

```bash
# from a host with sqlite3, pointed at the volume path:
sqlite3 <volume>/samepage.db ".backup '<dest>/samepage-$(date -u +%Y%m%dT%H%M%SZ).db'"
```

`deploy/backup.sh` wraps this with an integrity check + retention prune, and
`deploy/restore-check.sh` proves the newest backup restores at Alembic head —
run them from a checkout with `sqlite3` installed, pointed at the volume. A
backup you've never restored is a hope, not a backup.

## Upgrades

Land the change on `main`, take a backup, then redeploy in Coolify. Migrations
are forward-only in practice; restoring a backup is the real rollback.
