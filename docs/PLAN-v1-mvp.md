# Dinner Decider — v1 MVP Implementation Plan

> Status: **Plan 1 — committed 2026-08-26, awaiting charter approval** · Owner: Bartowski (lead) · Concept source: `README.md` · Charter: `CHARTER.md`
>
> Incorporated 2026-08-26: [`docs/INITIAL-PLAN-REVIEW.md`](INITIAL-PLAN-REVIEW.md) — all 12 findings accepted and applied (roster freeze, Alembic migrations, WAL-safe backups, lunch-track seed, admin/security, strengthened privacy, README truthfulness, deployment wording, recipe-use experience, fixed batch size, idempotency, deactivate-not-delete).
>
> This document is the reference for implementation. Decisions in §3 are **locked unless marked reviewable** — the implementer follows this spec; it does not make product decisions.

---

## 1. Goal

Build the first useful version of Dinner Decider: a household web app for **weekly meal planning**. The household sets how many dinners and lunches the week needs; the app runs iterative batches of 15 meal options with private yes/no votes, keeps only the meals everyone said yes to, and repeats until the week's plan is complete. The meal library ships **pre-seeded** from the legacy spreadsheet. **No AI, no dice, no import feature, no grocery list** in v1.

## 2. Scope

**In:**

1. Household profiles (people + PINs, no accounts)
2. Meal library — meals have **title, type (lunch/dinner/both), category, tags, recipe (link/text)**
3. **Pre-seeded** meal library from the legacy spreadsheet (including the recipe links it contains)
4. Planning session: set **lunch and dinner targets** for the week
5. Iterative voting batches: **15 meal options per batch, same list for every participant**, private **yes/no** votes
6. Results: meals where **everyone said yes** are kept; another batch is presented until targets are met
7. Record of **successful matches** (`times_kept`, `last_kept_at`, raw votes) → the seeds of favorites
8. Session history
9. Manual meal add/edit/archive

**Out (explicit):** grocery/shopping list (feeds it, doesn't build it), recipe ingestion/parsing (future AI step), import UI/CLI, dice-roll ritual, non-binary vote shades, preference learning, accounts/multi-household, mobile apps.

## 3. Locked decisions (reviewable before M0)

| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | **Stack** | Python 3.12+ · uv · FastAPI · SQLAlchemy 2.x · SQLite · Jinja2 templates · HTMX + minimal vanilla JS · uvicorn | One-language, zero frontend build step, single-file DB, runs on any box in the house. Easy to spec precisely. |
| D2 | **Identity** | No accounts. `Person` = name + 4-digit PIN, **stored hashed** (PBKDF2, per-person salt — stdlib). Signed-cookie session stores `person_id` per device. | Privacy of votes without an account system. Hashed because the app is internet-facing (review #5). |
| D3 | **Session codes** | `WORD-####` (e.g. `TACO-1234`), food-themed ~100-word list, easy-to-spell words only | Mirrors Pips' `generateCode()` (`WORD-NUMBER`); short enough to read aloud across a room. |
| D4 | **Vote scale** | Binary `yes` / `no` | Charlie's direction. No "not tonight" shades in MVP. |
| D5 | **Keep rule & roster** | The participant roster **freezes when the starter begins voting** (lobby phase first; late join disallowed in v1). A meal qualifies iff **every required participant has an explicit `yes` vote** on it. Auto-close requires every roster member to vote on every meal; manual close treats missing votes as `no`. | Review #1: unanimity must be defined over a fixed roster, not "whoever happened to vote". |
| D6 | **Batch assembly** | **15 options per batch, fixed** — an implementation tuning parameter, not a household setup choice (revisit after real use). Pool = active meals of the active track (`type == track` or `type == "both"`), **minus any meal already voted on in this session**; shuffled, take `min(15, len(pool))`. | Review #10: batch size is tuning, not a planning decision. No repeats within a session. |
| D7 | **Pre-seeding** | `seed/meals.json` (committed; generated from the spreadsheet) + `scripts/seed.py` loader. **No import feature** — the spreadsheet is a one-time source, not a user flow. | Charlie: "No need to import the spreadsheet… I want all of that pre-seeded." |
| D8 | **Tags & categories** | First-class metadata: category (`Tab 1..8`, renamable) + free tags. Seed auto-tags the 10 known takeout meals. Purpose: organization now, **AI discovery hooks later**. | Charlie: "tags… so that we can pin on ai discovery steps later." |
| D9 | **Favorites signal** | `meal.times_kept += 1` and `last_kept_at = now` on every keep; all raw votes stored. Favorites are *derived* from successful matches over time — no manual star list in MVP. | Charlie: "keep record of successful matches, so that we can start to determine favorites." |
| D10 | **Tracks** | Meal type `lunch` / `dinner` / `both`. Session sets `lunch_target` + `dinner_target`. Tracks run **dinner first, then lunch** (both unmet → dinner; next unmet → lunch). A `both` meal counts toward either track. **The seed carries a curated `both` subset (27 meals) so the lunch track is populated from a fresh install.** | "Meals are lunch and dinner; before beginning, the target number for each is set." Review #4: no intentionally empty core track. |
| D11 | **Seed dedupe** | Loader dedupes by `normalized_name` (casefold + collapsed whitespace): first occurrence wins, exact duplicates logged and skipped. | The spreadsheet has "Chicken parm" twice (Tabs 1 & 2) — same meal, not two meals. |
| D12 | **Polling, not websockets** | Page refresh / short poll on session pages | 2–6 people; realtime push is overkill. |
| D13 | **Over-target keeps** | If unanimous-yes meals exceed remaining slots, the starter chooses which to keep (multi-select, max = remaining). Kept = counted; dropped = recorded as voted, not kept. | A batch can agree on more than the week needs; the household picks. |
| D14 | **Deployment** | **VPS-hosted** (Hostinger) behind HTTPS (Caddy auto-TLS); household passphrase (`DD_ACCESS_KEY`, once per device) as the access gate; **backups via the SQLite backup API / `VACUUM INTO` (WAL-safe — never a raw copy of a live `.db`), restore verified in M5**; provider snapshots. | Review #3: WAL + raw file copy is not a reliable backup. |
| D15 | **Migrations** | **Alembic from M0**; every schema change after initial creation ships as a migration (`create_all` is dev/test only). | Review #2: durable family data with a long growth path (v1.5/v2). |
| D16 | **Administration & security** | `Person.is_admin` gates admin actions (managing people, changing PINs, archiving/unarchiving meals, maintenance ops). Secure cookie flags (`Secure`, `HttpOnly`, `SameSite`) + CSRF/origin checks on state-changing requests; PIN-verify attempt limiting. **People are deactivated, never deleted.** | Review #5/#12: internet-facing app; admin boundaries; history preserved. |

## 4. Legacy spreadsheet state (evidence, audited 2026-08-26)

Full audit: `reference/README.md`. Facts that shaped the seed:

- 8 sheets, header `Roll Result | Dinner | Times Rolled`, up to 20 meal rows; sheet position = D8, row = D20.
- **~155 named meals**; Sheet8 has only 15 (rows 16–20 empty — tolerated).
- **`Times Rolled` column is ignored** (Charlie's direction) — not carried into the seed.
- **4 recipe URLs**: 2 standalone cells (TikTok in Sheet2 col E, damndelicious in Sheet8 col D), 2 embedded in meal names (cookincanuck Sheet5, allrecipes Sheet6 — seed strips them into `source_url`).
- 10 takeout entries → auto-tagged `takeout` (legitimate dinner answers, not noise).
- Catch-alls ("Make do", "Leftovers", "yesterday's chicken") — ordinary meals.
- **One exact duplicate**: "Chicken parm" (Tab 1 & 2) → seed dedupe (D11). Near-duplicates (Chili family) kept as-is.
- Two `(LC)`-suffixed entries — names preserved verbatim.

## 5. User stories (MVP)

| ID | Story | Acceptance |
|---|---|---|
| US1 | As the admin, I install the app and it already has the household's meals | `uv run scripts/seed.py` → 155 meals, 8 categories, 4 with recipe links, 10 tagged takeout, chicken-parm dup logged |
| US2 | As the admin, I add/edit/archive meals with title, type, category, tags, recipe | CRUD works; archived meals leave session pools |
| US3 | As anyone, I start a planning session: set dinners + lunches targets, share the code | Session created in lobby with code; targets stored |
| US4 | As a household member, I join the lobby by code, identify with my PIN; once the starter begins voting, the roster is frozen and I vote yes/no on the same 15-meal batch as everyone else | Late join rejected once voting started; I see the same 15 meals; my votes are private — and never shown even after the batch closes |
| US5 | As the starter, I begin voting (roster freezes), and later see the batch outcome | Only unanimous-yes meals shown as kept; no tallies, no individual votes; over-target → choose |
| US6 | As the household, we run batches until the week is planned | Target reached per track; session completes with a week summary |
| US7 | As anyone, I see past sessions and which meals were kept | History lists sessions with kept meals; meals show `times_kept` |
| US8 | As the admin, I fix a meal (retag, retype, edit recipe) | Edits reflect in future sessions |
| US9 | As the admin, I manage people: add, change PINs, deactivate (never delete) | Inactive people can't join sessions; history preserved |

## 6. Data model (SQLite via SQLAlchemy 2.x declarative)

```
person(id PK, name TEXT UNIQUE NOT NULL, pin_hash TEXT NOT NULL,    -- PBKDF2 hash of 4-digit PIN (D2)
       is_admin BOOL DEFAULT 0,                                     -- admin flag (D16)
       is_active BOOL DEFAULT 1, created_at DATETIME)               -- deactivate, never delete (D16)

category(id PK, name TEXT UNIQUE NOT NULL, sort_order INT,         -- "Tab 1".."Tab 8" from seed
         legacy_sheet_index INT NULL)                               -- 1..8; NULL for user-made

tag(id PK, name TEXT UNIQUE NOT NULL)

meal(id PK, name TEXT NOT NULL, normalized_name TEXT NOT NULL,     -- casefold+collapse, dedupe key
     type TEXT NOT NULL DEFAULT 'dinner',                          -- lunch|dinner|both (D10)
     description TEXT, source_url TEXT, recipe_text TEXT,          -- recipe = link and/or text
     category_id FK -> category,
     is_active BOOL DEFAULT 1, archived_at DATETIME NULL,
     times_kept INT DEFAULT 0, last_kept_at DATETIME NULL,         -- favorites signal (D9)
     created_at DATETIME, updated_at DATETIME)

meal_tag(meal_id FK, tag_id FK, PK(meal_id, tag_id))

session(id PK, code TEXT UNIQUE NOT NULL,                          -- WORD-####
        status TEXT NOT NULL,                                      -- lobby|voting|complete|expired
        created_by_person_id FK -> person,
        lunch_target INT NOT NULL, dinner_target INT NOT NULL,     -- D10
        created_at DATETIME, finished_at DATETIME NULL)

session_participant(session_id FK, person_id FK, joined_at DATETIME, PK(session_id, person_id))

batch(id PK, session_id FK, seq INT, track TEXT NOT NULL,          -- lunch|dinner (D10)
      status TEXT NOT NULL DEFAULT 'open',                         -- open|closed
      closed_at DATETIME NULL, UNIQUE(session_id, seq))

batch_meal(batch_id FK, meal_id FK, sort_order INT, kept BOOL DEFAULT 0,
           PK(batch_id, meal_id))

vote(id PK, batch_id FK, person_id FK, meal_id FK,
     choice TEXT NOT NULL,                                         -- 'yes'|'no' (D4)
     created_at DATETIME, UNIQUE(batch_id, person_id, meal_id))
```

Notes:
- Votes are stored raw (evidence for future learning) but are **never exposed in the normal UI, before or after batch closure** (D16 privacy invariant) — normal users see only aggregate outcomes.
- Kept meals: `batch_meal.kept = 1` → `meal.times_kept += 1`, `last_kept_at = now` (transactionally, in the keep step — see idempotency §9.8).
- **People are deactivated, never deleted** — there is no DELETE for people (D16); history and referential integrity are preserved.
- The batch size is a module constant (15), not a column (D6).
- No `legacy_rolls` anywhere — the Times Rolled column is deliberately ignored.

## 7. Architecture & app layout

### Why a backend (and why VPS-hosted)

The original concept conversation floated a "no backend" shape (static page, per-browser storage). It is the wrong shape for this product, for four concrete reasons:

1. **Private simultaneous voting requires server-enforced state.** Votes must stay hidden until a batch closes. Per-browser storage has no shared trusted state — either everyone votes on one device (zero privacy) or you bolt on a cloud sync layer, which *is* a backend, just one you don't control.
2. **The meal library is durable family data.** Dinner Decider is expected to become the family recipe keeper, replacing the hand-written dinner notebook in the kitchen. Per-browser storage is one cleared cache away from losing the notebook's contents. A server with a real DB file gives a single source of truth, backups, and a future export path.
3. **AI keys must never live in a browser.** Recipe intake/discovery (v2) needs an LLM; provider keys belong in server-side env vars, never in client JS.
4. **Data-size headroom is a non-issue.** Even a generous family library — thousands of recipes with ingredients, instructions, and notes — is a few MB of text in SQLite; images live as files on disk, not blobs. SQLite (WAL mode) handles a household's concurrent write rate trivially, and SQLAlchemy keeps any later Postgres migration a config change, not a rewrite.

The honest no-backend case is a single-device, throwaway, no-privacy app — not this one. The README's own architecture section describes a server shape ("desktop/web host or lightweight server… persistent local database"), and this plan commits to it: **a VPS-hosted backend** (FastAPI + SQLite) on Charlie's Hostinger VPS — **no local hosting**. The household reaches it from anywhere via HTTPS; no LAN or Tailscale dependency. The app itself is deployment-agnostic (uvicorn + SQLite); hosting details in §7.1.

### Layout

```
dinnerdecider/
├── app/
│   ├── main.py            # FastAPI app, middleware, route registration
│   ├── settings.py        # env-driven (DD_DB_PATH, DD_SECRET, DD_ACCESS_KEY, DD_PORT)
│   ├── db.py              # engine, SessionLocal, get_db dependency (Alembic-managed schema, D15)
│   ├── security.py        # PIN hashing (PBKDF2), origin/CSRF check middleware, cookie flags (D16)
│   ├── models.py          # SQLAlchemy models (§6)
│   ├── session_logic.py   # pure functions: batch assembly, unanimity over the frozen roster,  ← the testable core
│   │                      #   over-target keep resolution, track progression (idempotent)
│   ├── codes.py           # session-code generation (WORD-####, collision loop)
│   ├── routes/
│   │   ├── people.py  library.py  sessions.py  history.py
│   ├── templates/         # Jinja2 (base.html, people/, library/, sessions/, history/)
│   └── static/            # app.css, app.js (vanilla; HTMX via CDN or vendored)
├── alembic/               # migrations (initial schema + future changes, D15)
├── scripts/
│   ├── seed.py            # loads seed/meals.json into the DB (idempotent, D7/D11)
│   └── build_seed.py      # dev-time: regenerates seed/meals.json from reference/ (openpyxl, dev-only dep)
├── seed/meals.json        # pre-seeded library (committed, reviewable) + seed/README.md
├── tests/                 # pytest: unit (session_logic, codes, seed) + route smoke (TestClient)
├── pyproject.toml         # uv-managed; runtime deps: fastapi, uvicorn, sqlalchemy, alembic, jinja2,
│                          #   python-multipart; dev deps: pytest, httpx, ruff, openpyxl
├── .github/workflows/ci.yml
├── CHARTER.md ROADMAP.md CLAUDE.md REQUESTS.md
├── docs/                  # PLAN-v1-mvp.md, POST-V1.md, ORIGINAL-CONCEPT.md, DEVLOG.md
└── reference/             # legacy spreadsheet (read-only source)
```

- DB file default `data/dinnerdecider.db` (gitignored), overridable via `DD_DB_PATH`.
- Templates server-rendered; voting interactions are `hx-post` calls; batch progress via short polling (D12).
- **No Node, no bundler, no build step.** HTMX vendored as a static file.

### 7.1 Deployment (VPS)

- **Target**: Charlie's Hostinger Ubuntu VPS (where Hermes already runs). The app is **internet-facing from day one** — no local hosting, no LAN/Tailscale dependency. Responsive web UI means family phones just need a browser and the URL.
- **HTTPS**: Caddy reverse proxy with auto-TLS (Let's Encrypt). Domain: a subdomain of an existing owned domain (e.g. `dinner.*`) — M5 ops detail.
- **Run**: Docker Compose (app + Caddy) *or* plain systemd + Caddy — decided at M5; the app itself is just uvicorn + SQLite either way.
- **Access gate** (reviewable): a single **household passphrase** (`DD_ACCESS_KEY`, env var) entered once per device before first use. Keeps a public app closed to random internet traffic while preserving the no-accounts, PIN-based household UX. ~30 lines of middleware + a first-use screen.
- **Data & backups**: SQLite at `data/dinnerdecider.db` on the VPS (WAL mode). Backups use a **WAL-safe mechanism — the SQLite backup API or `VACUUM INTO` — never a raw copy of a live `.db`** (D14, review #3). Daily job, keep N, plus provider snapshots. **M5 verifies restore**: a backup is restored into a fresh instance and the app reads it.
- **Env**: `DD_SECRET` (session signing, random), `DD_ACCESS_KEY`, `DD_DB_PATH`, `DD_PORT`.

## 8. Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Home: new session CTA, active session link, library/history/people links |
| GET/POST | `/people` · `/people/{id}` | Household profiles CRUD (admin-only: name, PIN, active) |
| GET | `/library` | Meal library: search, filter by type/category/tag, archived toggle, `times_kept` visible |
| GET/POST | `/library/new` · `/library/{id}/edit` | Meal create/edit (title, type, category, tags, recipe link/text) |
| POST | `/library/{id}/archive` · `/unarchive` | Manual archive (US2; admin-only) |
| GET | `/sessions/new` | Session setup: lunch target, dinner target (batch size is fixed at 15, not a choice) |
| POST | `/sessions` | Create session (lobby) → 303 to `/s/{code}` |
| GET | `/s/{code}` | Session page: join gate → lobby (roster forming) / voting / batch outcome / week summary (status-aware) |
| POST | `/s/{code}/join` | Join the lobby as person (name + PIN) → session participant |
| POST | `/s/{code}/start` | Starter begins voting → **roster freezes**, first batch created (D5) |
| POST | `/s/{code}/vote` | `{batch_id, meal_id, choice}` — upsert vote (US4) |
| POST | `/s/{code}/close-batch` | Starter forces batch close (unvoted = no) |
| POST | `/s/{code}/keep` | `{meal_ids: []}` — resolve over-target keeps (D13) |
| POST | `/s/{code}/next` | Advance: next batch for the track, or next track, or complete |
| POST | `/s/{code}/finish` | Mark session complete (targets met) |
| GET | `/history` | Completed sessions, newest first, with kept meals per track |
| POST | `/sessions/expire-stale` | (ops) mark sessions older than 24h as expired |

## 9. Session lifecycle (the core algorithm)

### 9.1 Setup (lobby)

`/sessions/new`: starter sets `dinner_target` and `lunch_target` (batch size is fixed at 15 — not a household choice, D6). POST creates the session in **`lobby`** with a code (D3). The starter shares the code; household members join the lobby (`/join`, name + PIN). **The roster is whoever is in the lobby when the starter begins voting.**

### 9.2 Start voting (roster freeze — review #1)

POST `/s/{code}/start` (starter only): the participant roster **freezes** (D5). Late join after this point is rejected ("voting already started" — v1: sit this one out or start your own session). Status → `voting`; the **first batch** is created for the active track (dinner if `dinner_target > 0`, else lunch).

### 9.3 Batch assembly (exact)

```
pool = active meals where (type == track or type == "both")
       and meal NOT IN (meals already in any batch of this session)
batch = shuffle(pool)[:min(15, len(pool))]                          # D6: fixed 15
```

- If `pool` is empty → the track is stuck: show the household a clear message + CTA ("add meals / retag meals as this type / lower the target"), offer to finish the session with the current plan. Never a dead end.
- Batch `seq` increments per batch; a batch belongs to exactly one track.

### 9.4 Voting

- Every roster member sees the **same batch** of meal cards (name, category, tags, type, recipe link if present, `times_kept` as "kept N× before").
- Each member votes `yes`/`no` per meal (one tap each; can change until the batch closes).
- **Auto-close** when every **roster member** has voted on every meal in the batch. **Manual close** by starter anytime (missing votes count as `no`).
- **Privacy invariant (strong — D16, review #6)**: individual votes are **never exposed in the normal UI, before or after batch closure**. During voting, no client response contains any vote data other than the caller's own. After close, normal users see only **aggregate outcomes**: unanimous-yes meals (kept), no-match state, meals ultimately kept. No tallies, no "x of y voted", no "who said no". Raw votes stay server-side for future learning/diagnostics.

### 9.5 Batch results & keeps (exact)

```
roster = frozen participants (joined before start)
unanimous = [meal in batch where EVERY roster member voted 'yes' on it]   # D5
remaining_slots = track_target - kept_so_far(track)
kept = unanimous[:remaining_slots] if len(unanimous) <= remaining_slots
       else starter chooses via /keep (max remaining_slots)          # D13
```

- Kept meals: `batch_meal.kept=1`, `meal.times_kept += 1`, `last_kept_at = now` (in the keep transition — idempotent, §9.9).
- Unanimous-but-not-kept (over-target rejects) are recorded as voted, not kept.

### 9.6 Progression

```
if track target met → switch to the other track if it still has a target → else complete
else → next batch (seq + 1) for the same track
```

### 9.7 Completion

`status=complete`, `finished_at=now`. Final screen = **the week's plan**: kept dinners list + kept lunches list, plus a link to history. This plan output is what feeds grocery planning done elsewhere (out of scope).

### 9.8 Expiry

Sessions in `lobby` or `voting` older than 24h are treated as `expired` (lazy check on access + a cleanup endpoint). History only shows `complete` sessions.

### 9.9 Idempotency (review #11)

`close-batch`, `keep`, `next`, and `finish` must be safe against double-submit and concurrent requests:

- Every transition is guarded by a status check **inside the transaction** (close only when the batch is open; keep only when the batch is closed and keeps not yet recorded; next only when the current batch is closed; finish only when targets are met).
- A duplicate request returns the current state (200, same result) — it never applies the transition twice.
- `times_kept` increments only inside the atomic keep transition.
- Tests: fire each transition twice (and concurrently); assert it applies exactly once.

## 10. Seed pipeline (replaces any import feature)

- **`seed/meals.json`** (committed): 155 meals; schema + decisions documented in `seed/README.md`. Reviewable via diff.
- **`scripts/build_seed.py`** (dev-time, M2): regenerates the JSON from `reference/D20 Dinner Decider.xlsx` — strip embedded URLs → `source_url`, collapse whitespace, `Tab N` categories, takeout auto-tag, **type mapping: a curated 27-meal lunch-capable subset → `both`, the rest → `dinner`** (explicit list in `seed/README.md`, D10), Times Rolled ignored. Requires openpyxl (dev dependency only; **not a runtime dependency**).
- **`scripts/seed.py`** (runtime, M2): loads the JSON into an empty DB — creates categories, meals, tags; dedupes by `normalized_name` (D11), logs skips; idempotent (safe to re-run). Run once during setup (`uv run scripts/seed.py`); README documents it. If the DB already has meals, it reports and does nothing.
- Seed tests: 155 meals / 8 categories / 4 `source_url` / 10 takeout / chicken-parm dup logged / idempotent re-run / **lunch-track pool non-empty (27 `both`)**.

## 11. Milestones & tasks

Each milestone is one or more cycles; acceptance criteria + verification commands. **The lead re-runs everything — a green self-report is never accepted.**

### M0 — Foundation (≈1–2 cycles)

| Task | Acceptance |
|---|---|
| T0.1 Scaffold: `pyproject.toml` (uv), `.gitignore`, package layout | Fresh `uv sync` installs cleanly |
| T0.2 DB layer + settings (`DD_DB_PATH`, `DD_SECRET`, `DD_ACCESS_KEY`, `DD_PORT`) | DB created on boot; env overrides work |
| T0.3 Models (§6) + **Alembic initial migration** (D15) | `alembic upgrade head` builds the schema; `create_all` is dev/test only |
| T0.4 App skeleton: `main.py`, session middleware, **security middleware** (cookie flags, origin/CSRF check — D16), health route, base template, static | `/health` → 200; session cookie round-trips; state-changing POSTs without a matching origin rejected |
| T0.5 CI: `astral-sh/setup-uv`, `ruff check .`, `pytest -q` | CI green on push |

Verify: `uv run pytest -q` green · `uv run ruff check .` clean · `uv run uvicorn app.main:app` serves `/` · CI green.

### M1 — Household profiles (≈1–2 cycles)

| Task | Acceptance |
|---|---|
| T1.1 Person CRUD (admin-only) + templates: add, edit name/PIN, **deactivate (no delete)** | CRUD from UI; inactive people can't join; history preserved |
| T1.2 **Hashed PINs** (PBKDF2, per-person salt) + verify endpoint with **attempt limiting** | Wrong PIN rejected (and limited after N attempts); correct PIN sets session; no plaintext PIN anywhere |
| T1.3 **First person is admin** (empty-household bootstrap); `is_admin` gates people/archive routes | Admin actions denied for non-admins |
| T1.4 "Who am I" header | Clear identity on every page |

Verify: unit + route tests for CRUD, PIN gate + limiting, admin gating, session persistence.

### M2 — Meal library + pre-seeded data (≈3–4 cycles)

| Task | Acceptance |
|---|---|
| T2.1 Meal CRUD + library UI (title, type, category, tags, recipe link/text; search + filters) | Full CRUD; `times_kept` visible |
| T2.2 Archive/unarchive | Archived meals leave session pools (test) |
| T2.3 `scripts/build_seed.py` + regenerate + commit `seed/meals.json` | Regeneration matches the committed JSON (diff clean) |
| T2.4 `scripts/seed.py` (idempotent, dedupe, logging) + seed tests | US1 acceptance (§5) |

Verify: fresh DB → `uv run scripts/seed.py` → 155 meals, 8 categories, 4 URLs, 10 takeout, dup logged; re-run no-ops; seed tests green.

### M3 — Planning sessions & voting (≈6–8 cycles — the core loop)

| Task | Acceptance |
|---|---|
| T3.1 Session creation: targets → code, status `lobby` | Code unique; targets stored; lobby state |
| T3.2 Join the lobby: code → person → PIN → participant | Non-participants blocked; PIN required |
| T3.3 **Start voting → roster freeze** (§9.2) | Late join rejected after start; first batch created |
| T3.4 Batch assembly (§9.3) | Correct pool; no repeats within session; stuck-track path works |
| T3.5 Vote UI: same cards for everyone; yes/no; change-until-close | One-tap voting; per-card state |
| T3.6 Vote endpoint upsert + **strong privacy** (§9.4) | Test: no other person's votes in any response — during voting **or after close** |
| T3.7 Batch close (auto + manual) → unanimity over roster → keeps (incl. over-target `/keep`) | Correct keeps for table-driven cases; counters update (D9) |
| T3.8 **Idempotency** (§9.9): double-submit close/keep/next/finish | Each transition applies exactly once; `times_kept` not double-incremented |
| T3.9 Track progression + completion + week summary (§9.6–9.7) | Full session ends with the week's plan |

Verify: **two-browser walkthrough** (create lobby → join ×2 → start (roster freezes) → vote → close → keeps → next batch → … → targets met → summary); stuck-track, over-target, late-join, and double-submit cases exercised; privacy test green.

### M4 — History & favorites signal (≈2 cycles)

| Task | Acceptance |
|---|---|
| T4.1 History page: completed sessions with kept meals per track (US7) | Correct rows incl. meal/date/targets |
| T4.2 Library `times_kept` / `last_kept_at` + "most kept" sort | Counters correct after sessions |
| T4.3 Empty/error states (no meals of a type, no sessions, unknown code) | No 500s; friendly messages |

### M5 — Hardening, polish, deployment docs (≈3 cycles)

| Task | Acceptance |
|---|---|
| T5.1 Responsive pass — phones are the critical path (vote screen) | Vote screen usable at 360px width |
| T5.2 Local run docs: README "Run it" (uv sync → seed → uvicorn), troubleshooting | Fresh clone → running in 3 commands |
| T5.3 VPS deployment: Docker Compose/systemd + Caddy HTTPS, env vars, **WAL-safe backup job** (`VACUUM INTO` / backup API, keep N) per §7.1 | Fresh VPS deploy from the docs lands a working HTTPS app; **restore test: a backup is restored into a fresh instance and the app reads it** |
| T5.4 Access gate: `DD_ACCESS_KEY` middleware + first-use screen (reviewable) | App unreachable without passphrase; remembered per device |
| T5.5 Final verification: full suite + ruff + fresh-checkout run + walkthrough checklist | DoD (§15) all checked |
| T5.6 (optional) seed/demo script | Not required for DoD |

## 12. Testing & CI strategy

- **Unit (pytest)**: `session_logic` — batch assembly (pool filter, no-repeat, 15-cap), unanimity over the **frozen roster** (all-yes, one no, missing vote = no, empty roster edge), over-target keep resolution, track progression (dinner→lunch→complete, stuck track), **idempotent transitions** (double-submit close/keep/next/finish), codes (format + uniqueness), seed (counts, dedupe, idempotency, lunch pool non-empty).
- **Integration**: full session flow via FastAPI `TestClient` (US1–US9 smoke); seed against a temp DB; admin gating (non-admin blocked from people/archive routes); PIN hashing + attempt limiting.
- **Privacy test** (M3): assert no vote data other than the caller's own appears in any response — during voting **and after batch closure**.
- **CI**: GitHub Actions — setup-uv, `uv sync`, `alembic upgrade head` on a fresh DB, `ruff check .`, `pytest -q`, on push + PR.
- **Rule**: the lead re-runs everything; a green self-report is never accepted.

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Unanimous-yes keeps too rare → session stalls | Graceful stuck-track/stall paths; over-target keeps; manual finish; pivot to looser keep rules tracked for post-MVP, not improvised |
| Roster freeze leaves someone out | Lobby is explicit ("who's in?"); late join rejected with a clear message; they can start their own session or join next week — tracked as a v1 constraint, revisit after use |
| Vote privacy leaks | Strong invariant (D16): individual votes never rendered to any client, before or after close; no tally in any response; cookie httponly + secure flags; origin/CSRF checks on state-changing requests |
| Over-target batches create friction | `/keep` multi-select, capped at remaining slots |
| Backup restores fail silently | WAL-safe backup mechanism (D14); M5 restore verification is a hard acceptance |
| Scope creep (grocery list, recipe parsing, AI) | Explicit non-goals + stop criteria + REQUESTS channel |
| Household doesn't adopt it | Success criterion is real usage; stop criteria explicit; MVP is small |

## 14. Open questions (resolve through use; per Charlie's original note, don't design to death)

| Question | MVP default | When to revisit |
|---|---|---|
| Batch size | **Fixed at 15** (D6, review #10) | After real sessions |
| Track order | Dinner first, then lunch | After real sessions |
| Does a `both` meal count toward either track? | Yes | After real sessions |
| Over-target keeps | Starter chooses | After real sessions |
| Favorites threshold | `times_kept` count, no threshold in MVP | When favorites surface (V2) |
| Should the dice ritual return as a fun pick? | Out of MVP | Charlie's call; POST-V1 "later" list |
| Lunch `both` subset curation (27 meals) | Curated list in `seed/README.md`, adjustable | Charlie's veto welcome; after real use |

## 15. Definition of done & stop criteria

DoD: **CHARTER.md §"Definition of done"** — weekly sessions with pre-seeded library, private yes/no batches, unanimous keeps until targets met, kept records + history, meal CRUD/archive. Stop criteria: **CHARTER.md §"Stop criteria"** — budget (25 cycles), non-adoption after a fair trial (2–3 sessions), chronically stalled sessions, or Charlie's call.

**Approval gate:** this plan and the charter are pending Charlie's sign-off. M0 does not start until approval.
