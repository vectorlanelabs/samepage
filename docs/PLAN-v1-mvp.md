# Dinner Decider — v1 MVP Implementation Plan

> Status: **Plan 1 — committed 2026-08-26, awaiting charter approval** · Owner: Bartowski (lead) · Concept source: `README.md` · Charter: `CHARTER.md`
>
> This document is the reference for implementation. Decisions in §3 are **locked unless marked reviewable** — the implementer follows this spec; it does not make product decisions.

---

## 1. Goal

Build the first useful version of Dinner Decider: a household web app for **weekly meal planning**. The household sets how many dinners and lunches the week needs; the app runs iterative batches of 15–20 meal options with private yes/no votes, keeps only the meals everyone said yes to, and repeats until the week's plan is complete. The meal library ships **pre-seeded** from the legacy spreadsheet. **No AI, no dice, no import feature, no grocery list** in v1.

## 2. Scope

**In:**

1. Household profiles (people + PINs, no accounts)
2. Meal library — meals have **title, type (lunch/dinner/both), category, tags, recipe (link/text)**
3. **Pre-seeded** meal library from the legacy spreadsheet (including the recipe links it contains)
4. Planning session: set **lunch and dinner targets** for the week
5. Iterative voting batches: **15–20 meal options, same list for every participant**, private **yes/no** votes
6. Results: meals where **everyone said yes** are kept; another batch is presented until targets are met
7. Record of **successful matches** (`times_kept`, `last_kept_at`, raw votes) → the seeds of favorites
8. Session history
9. Manual meal add/edit/archive

**Out (explicit):** grocery/shopping list (feeds it, doesn't build it), recipe ingestion/parsing (future AI step), import UI/CLI, dice-roll ritual, non-binary vote shades, preference learning, accounts/multi-household, mobile apps.

## 3. Locked decisions (reviewable before M0)

| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | **Stack** | Python 3.12+ · uv · FastAPI · SQLAlchemy 2.x · SQLite · Jinja2 templates · HTMX + minimal vanilla JS · uvicorn | One-language, zero frontend build step, single-file DB, runs on any box in the house. Easy to spec precisely. |
| D2 | **Identity** | No accounts. `Person` = name + 4-digit PIN. Signed-cookie session stores `person_id` per device. | Privacy of votes without an account system. |
| D3 | **Session codes** | `WORD-####` (e.g. `TACO-1234`), food-themed ~100-word list, easy-to-spell words only | Mirrors Pips' `generateCode()` (`WORD-NUMBER`); short enough to read aloud across a room. |
| D4 | **Vote scale** | Binary `yes` / `no` | Charlie's direction. No "not tonight" shades in MVP. |
| D5 | **Keep rule** | A meal is kept iff **every participant who voted in the batch voted `yes`** on it. Participants who never vote don't block (starter can close; unvoted = no). | "Meals where everyone said yes only." Simple, explainable, testable. |
| D6 | **Batch assembly** | Batch size **15–20, default 15** (set at session creation). Pool = active meals of the active track (`type == track` or `type == "both"`), **minus any meal already voted on in this session**; shuffled, take `min(batch_size, len(pool))`. | "15–20 yes/no meal options… same list for each person… until the count is achieved." No repeats within a session. |
| D7 | **Pre-seeding** | `seed/meals.json` (committed; generated from the spreadsheet) + `scripts/seed.py` loader. **No import feature** — the spreadsheet is a one-time source, not a user flow. | Charlie: "No need to import the spreadsheet… I want all of that pre-seeded." |
| D8 | **Tags & categories** | First-class metadata: category (`Tab 1..8`, renamable) + free tags. Seed auto-tags the 10 known takeout meals. Purpose: organization now, **AI discovery hooks later**. | Charlie: "tags… so that we can pin on ai discovery steps later." |
| D9 | **Favorites signal** | `meal.times_kept += 1` and `last_kept_at = now` on every keep; all raw votes stored. Favorites are *derived* from successful matches over time — no manual star list in MVP. | Charlie: "keep record of successful matches, so that we can start to determine favorites." |
| D10 | **Tracks** | Meal type `lunch` / `dinner` / `both`. Session sets `lunch_target` + `dinner_target`. Tracks run **dinner first, then lunch** (both unmet → dinner; next unmet → lunch). A `both` meal counts toward either track. | "Meals are lunch and dinner; before beginning, the target number for each is set." |
| D11 | **Seed dedupe** | Loader dedupes by `normalized_name` (casefold + collapsed whitespace): first occurrence wins, exact duplicates logged and skipped. | The spreadsheet has "Chicken parm" twice (Tabs 1 & 2) — same meal, not two meals. |
| D12 | **Polling, not websockets** | Page refresh / short poll on session pages | 2–6 people; realtime push is overkill. |
| D13 | **Over-target keeps** | If unanimous-yes meals exceed remaining slots, the starter chooses which to keep (multi-select, max = remaining). Kept = counted; dropped = recorded as voted, not kept. | A batch can agree on more than the week needs; the household picks. |

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
| US3 | As anyone, I start a planning session: set dinners + lunches targets | Session created with code; targets stored |
| US4 | As a household member, I join by code, identify with my PIN, and vote yes/no on the same batch as everyone else | I see the same 15–20 meals; my votes are private |
| US5 | As the starter, I see the batch results | Only unanimous-yes meals shown; no tallies; over-target → choose |
| US6 | As the household, we run batches until the week is planned | Target reached per track; session completes with a week summary |
| US7 | As anyone, I see past sessions and which meals were kept | History lists sessions with kept meals; meals show `times_kept` |
| US8 | As the admin, I fix a meal (retag, retype, edit recipe) | Edits reflect in future sessions |

## 6. Data model (SQLite via SQLAlchemy 2.x declarative)

```
person(id PK, name TEXT UNIQUE NOT NULL, pin TEXT NOT NULL,        -- 4-digit
       is_active BOOL DEFAULT 1, created_at DATETIME)

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
        status TEXT NOT NULL,                                      -- voting|complete|expired
        created_by_person_id FK -> person,
        lunch_target INT NOT NULL, dinner_target INT NOT NULL,     -- D10
        batch_size INT NOT NULL DEFAULT 15,                        -- 15..20 (D6)
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
- Votes are stored raw (evidence for future learning) but are **never rendered to any client until the batch is closed**.
- Kept meals: `batch_meal.kept = 1` → `meal.times_kept += 1`, `last_kept_at = now` (transactionally, in the keep step).
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
│   ├── settings.py        # env-driven (DD_DB_PATH, DD_SECRET, DD_PORT)
│   ├── db.py              # engine, SessionLocal, get_db dependency, init/create-all
│   ├── models.py          # SQLAlchemy models (§6)
│   ├── session_logic.py   # pure functions: batch assembly, unanimous computation,  ← the testable core
│   │                      #   over-target keep resolution, track progression
│   ├── codes.py           # session-code generation (WORD-####, collision loop)
│   ├── routes/
│   │   ├── people.py  library.py  sessions.py  history.py
│   ├── templates/         # Jinja2 (base.html, people/, library/, sessions/, history/)
│   └── static/            # app.css, app.js (vanilla; HTMX via CDN or vendored)
├── scripts/
│   ├── seed.py            # loads seed/meals.json into the DB (idempotent, D7/D11)
│   └── build_seed.py      # dev-time: regenerates seed/meals.json from reference/ (openpyxl, dev-only dep)
├── seed/meals.json        # pre-seeded library (committed, reviewable) + seed/README.md
├── tests/                 # pytest: unit (session_logic, codes, seed) + route smoke (TestClient)
├── pyproject.toml         # uv-managed; runtime deps: fastapi, uvicorn, sqlalchemy, jinja2,
│                          #   python-multipart; dev deps: pytest, httpx, ruff, openpyxl
├── .github/workflows/ci.yml
├── CHARTER.md ROADMAP.md CLAUDE.md REQUESTS.md
├── docs/                  # PLAN-v1-mvp.md, POST-V1.md, DEVLOG.md
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
- **Data & backups**: SQLite at `data/dinnerdecider.db` on the VPS. Scheduled backup job (daily DB copy, keep N) + VPS provider snapshots — the library is irreplaceable family data (§7 point 2).
- **Env**: `DD_SECRET` (session signing, random), `DD_ACCESS_KEY`, `DD_DB_PATH`, `DD_PORT`.

## 8. Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Home: new session CTA, active session link, library/history/people links |
| GET/POST | `/people` · `/people/{id}` | Household profiles CRUD (name, PIN, active) |
| GET | `/library` | Meal library: search, filter by type/category/tag, archived toggle, `times_kept` visible |
| GET/POST | `/library/new` · `/library/{id}/edit` | Meal create/edit (title, type, category, tags, recipe link/text) |
| POST | `/library/{id}/archive` · `/unarchive` | Manual archive (US2) |
| GET | `/sessions/new` | Session setup: lunch target, dinner target, batch size (15–20) |
| POST | `/sessions` | Create session → 303 to `/s/{code}` |
| GET | `/s/{code}` | Session page: join gate → active batch voting / batch results / week summary (status-aware) |
| POST | `/s/{code}/join` | Join as person (name + PIN) → session |
| POST | `/s/{code}/vote` | `{batch_id, meal_id, choice}` — upsert vote (US4) |
| POST | `/s/{code}/close-batch` | Starter forces batch close (unvoted = no) |
| POST | `/s/{code}/keep` | `{meal_ids: []}` — resolve over-target keeps (D13) |
| POST | `/s/{code}/next` | Advance: next batch for the track, or next track, or complete |
| POST | `/s/{code}/finish` | Mark session complete (targets met) |
| GET | `/history` | Completed sessions, newest first, with kept meals per track |
| POST | `/sessions/expire-stale` | (ops) mark sessions older than 24h as expired |

## 9. Session lifecycle (the core algorithm)

### 9.1 Setup

`/sessions/new`: starter sets `dinner_target`, `lunch_target`, `batch_size` (15–20, default 15). POST creates the session (`status=voting`, code per D3). The **active track starts as `dinner`** if `dinner_target > 0`, else `lunch` (D10).

### 9.2 Batch assembly (exact)

```
pool = active meals where (type == track or type == "both")
       and meal NOT IN (meals already in any batch of this session)
batch = shuffle(pool)[:min(batch_size, len(pool))]
```

- If `pool` is empty → the track is stuck: show the household a clear message + CTA ("add meals / retag meals as this type / lower the target"), offer to finish the session with the current plan. Never a dead end.
- Batch `seq` increments per batch; a batch belongs to exactly one track.

### 9.3 Voting

- Every session participant sees the **same batch** of meal cards (name, category, tags, type, recipe link if present, `times_kept` as "kept N× before").
- Each participant votes `yes`/`no` per meal (one tap each; can change until batch closes).
- **Auto-close** when every participant has voted on every meal in the batch. **Manual close** by starter anytime (unvoted meals count as `no`).
- **Privacy invariant**: no client response during voting contains any vote data other than the caller's own. No tallies, no "x of y voted".

### 9.4 Batch results & keeps (exact)

```
voters = participants in session who voted at least once in this batch
unanimous = [meal in batch where every voter voted 'yes' on it]
remaining_slots = track_target - kept_so_far(track)
kept = unanimous[:remaining_slots] if len(unanimous) <= remaining_slots
       else starter chooses via /keep (max remaining_slots)          # D13
```

- Kept meals: `batch_meal.kept=1`, `meal.times_kept += 1`, `last_kept_at = now`.
- Unanimous-but-not-kept (over-target rejects) are recorded as voted, not kept.

### 9.5 Progression

```
if track target met → switch to the other track if it still has a target → else complete
else → next batch (seq + 1) for the same track
```

### 9.6 Completion

`status=complete`, `finished_at=now`. Final screen = **the week's plan**: kept dinners list + kept lunches list, plus a link to history. This plan output is what feeds grocery planning done elsewhere (out of scope).

### 9.7 Expiry

Sessions in `voting` older than 24h are treated as `expired` (lazy check on access + a cleanup endpoint). History only shows `complete` sessions.

## 10. Seed pipeline (replaces any import feature)

- **`seed/meals.json`** (committed): 155 meals; schema + decisions documented in `seed/README.md`. Reviewable via diff.
- **`scripts/build_seed.py`** (dev-time, M2): regenerates the JSON from `reference/D20 Dinner Decider.xlsx` — strip embedded URLs → `source_url`, collapse whitespace, `Tab N` categories, takeout auto-tag, `type: "dinner"` for all, Times Rolled ignored. Requires openpyxl (dev dependency only; **not a runtime dependency**).
- **`scripts/seed.py`** (runtime, M2): loads the JSON into an empty DB — creates categories, meals, tags; dedupes by `normalized_name` (D11), logs skips; idempotent (safe to re-run). Run once during setup (`uv run scripts/seed.py`); README documents it. If the DB already has meals, it reports and does nothing.
- Seed tests: 155 meals / 8 categories / 4 `source_url` / 10 takeout / chicken-parm dup logged / idempotent re-run.

## 11. Milestones & tasks

Each milestone is one or more cycles; acceptance criteria + verification commands. **The lead re-runs everything — a green self-report is never accepted.**

### M0 — Foundation (≈1–2 cycles)

| Task | Acceptance |
|---|---|
| T0.1 Scaffold: `pyproject.toml` (uv), `.gitignore`, package layout | Fresh `uv sync` installs cleanly |
| T0.2 DB layer + settings (`DD_DB_PATH`, `DD_SECRET`, `DD_PORT`) | DB created on boot; env overrides work |
| T0.3 Models: all §6 tables | Create-all works; models import clean |
| T0.4 App skeleton: `main.py`, session middleware, health route, base template, static | `/health` → 200; session cookie round-trips |
| T0.5 CI: `astral-sh/setup-uv`, `ruff check .`, `pytest -q` | CI green on push |

Verify: `uv run pytest -q` green · `uv run ruff check .` clean · `uv run uvicorn app.main:app` serves `/` · CI green.

### M1 — Household profiles (≈1–2 cycles)

| Task | Acceptance |
|---|---|
| T1.1 Person CRUD routes + templates | CRUD from UI; inactive people can't join |
| T1.2 PIN verify → signed session | Wrong PIN rejected; correct PIN sets session |
| T1.3 "Who am I" header | Clear identity on every page |

Verify: unit + route tests for CRUD, PIN gate, session persistence.

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
| T3.1 Session creation: targets + batch size → code | Code unique; targets stored; active track = dinner |
| T3.2 Join flow: code → person → PIN → participant | Non-participant blocked from voting |
| T3.3 Batch assembly (§9.2) | Correct pool; no repeats within session; stuck-track path works |
| T3.4 Vote UI: same cards for everyone; yes/no; change-until-close | One-tap voting; per-card state |
| T3.5 Vote endpoint upsert + **privacy** (§9.3) | Test: no other person's votes in any voting-phase response |
| T3.6 Batch close (auto + manual) → unanimous computation → keeps (incl. over-target `/keep`) | Correct keeps for table-driven cases; counters update (D9) |
| T3.7 Track progression + completion + week summary (§9.5–9.6) | Full session ends with the week's plan |

Verify: **two-browser walkthrough** (start → join ×2 → vote → close → keeps → next batch → … → targets met → summary); stuck-track and over-target cases exercised; privacy test green.

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
| T5.3 VPS deployment: Docker Compose/systemd + Caddy HTTPS, env vars, **backup job** (daily DB copy, keep N) per §7.1 | Fresh VPS deploy from the docs lands a working HTTPS app; backup cron restores |
| T5.4 Access gate: `DD_ACCESS_KEY` middleware + first-use screen (reviewable) | App unreachable without passphrase; remembered per device |
| T5.5 Final verification: full suite + ruff + fresh-checkout run + walkthrough checklist | DoD (§15) all checked |
| T5.6 (optional) seed/demo script | Not required for DoD |

## 12. Testing & CI strategy

- **Unit (pytest)**: `session_logic` — batch assembly (pool filter, no-repeat, min cap), unanimous computation (all-yes, one no, non-voter, empty), over-target keep resolution, track progression (dinner→lunch→complete, stuck track), codes (format + uniqueness), seed (counts, dedupe, idempotency).
- **Integration**: full session flow via FastAPI `TestClient` (US1–US8 smoke); seed against a temp DB.
- **Privacy test** (M3): assert no vote data other than the caller's own appears in any voting-phase response.
- **CI**: GitHub Actions — setup-uv, `uv sync`, `ruff check .`, `pytest -q`, on push + PR.
- **Rule**: the lead re-runs everything; a green self-report is never accepted.

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Unanimous-yes keeps too rare → session stalls | Graceful stuck-track/stall paths; over-target keeps; manual finish; pivot to looser keep rules tracked for post-MVP, not improvised |
| Lunch track empty at seed (all meals are `dinner` type) | Clear CTA + "add/retag lunch meals" path in-app; REQUESTS.md tracks a starter lunch set |
| Vote privacy leaks | Results strictly server-gated until batch close; no tally in any response; cookie httponly |
| Over-target batches create friction | `/keep` multi-select, capped at remaining slots |
| Scope creep (grocery list, recipe parsing, AI) | Explicit non-goals + stop criteria + REQUESTS channel |
| Household doesn't adopt it | Success criterion is real usage; stop criteria explicit; MVP is small |

## 14. Open questions (resolve through use; per Charlie's original note, don't design to death)

| Question | MVP default | When to revisit |
|---|---|---|
| Batch size 15 vs 20 | 15, settable at session creation | After real sessions |
| Track order | Dinner first, then lunch | After real sessions |
| Does a `both` meal count toward either track? | Yes | After real sessions |
| Over-target keeps | Starter chooses | After real sessions |
| Favorites threshold | `times_kept` count, no threshold in MVP | When favorites surface (V2) |
| Should the dice ritual return as a fun pick? | Out of MVP | Charlie's call; POST-V1 "later" list |
| Lunch meal starter set | None — household adds/retags | REQUESTS.md |

## 15. Definition of done & stop criteria

DoD: **CHARTER.md §"Definition of done"** — weekly sessions with pre-seeded library, private yes/no batches, unanimous keeps until targets met, kept records + history, meal CRUD/archive. Stop criteria: **CHARTER.md §"Stop criteria"** — budget (25 cycles), non-adoption after a fair trial (2–3 sessions), chronically stalled sessions, or Charlie's call.

**Approval gate:** this plan and the charter are pending Charlie's sign-off. M0 does not start until approval.
