# Dinner Decider — v1 MVP Implementation Plan

> Status: **committed 2026-08-26, awaiting charter approval** · Owner: Bartowski (lead) · Scope source: `README.md` · Charter: `CHARTER.md`
>
> This document is the reference for implementation. Every design decision in §3 is **locked unless marked reviewable** — the implementer follows this spec, it does not make product decisions.

---

## 1. Goal

Build the first useful version of Dinner Decider: a household web app that replaces the D8/D20 spreadsheet ritual with private common-ground voting plus an optional dice roll, and that records what the household actually eats. **The v1 needs no AI** (README "Suggested first version").

## 2. Scope

**In (the README's 10 V1 items, verbatim):**

1. Household profiles
2. Meal library
3. Import existing spreadsheet
4. Start dinner round
5. Private yes / not-tonight / no voting
6. Common-ground results
7. Random choice from accepted meals
8. Record what was chosen
9. Basic voting history
10. Archive meals manually

**Out (post-MVP — `docs/POST-V1.md`):** recipe ingestion (URL/paste/photo), printing, meal photo upload, preference learning, AI, pantry mode, accounts/multi-household, mobile apps. These are hard non-goals; touching them in MVP is scope creep.

## 3. Locked decisions (reviewable before M0)

| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | **Stack** | Python 3.12+ · uv · FastAPI · SQLAlchemy 2.x · SQLite · Jinja2 templates · HTMX + minimal vanilla JS · uvicorn | One-language, zero frontend build step, single-file DB, runs on any box in the house (Mac, Linux, Pi). Easy to spec precisely for cheap implementers. |
| D2 | **Identity** | No accounts. `Person` = name + 4-digit PIN. Signed-cookie session stores `person_id` per device. | README: authentication must not be a prerequisite for the household case. PIN preserves vote privacy without an account system. |
| D3 | **Round codes** | `WORD-####` (e.g. `TACO-1234`), food-themed ~100-word list, easy-to-spell words only | Mirrors Pips' `generateCode()` (`WORD-NUMBER`, e.g. `BONE-1234`); short enough to shout across the house, no ambiguous letters. |
| D4 | **Vote scale** | `yes` / `not_tonight` / `no` | README's four levels minus hard-no (V1.5). Enum is stored as text so a 4th value can be added without migration pain. |
| D5 | **Common-ground rule (MVP default)** | A meal survives iff **every participant who submitted ≥1 vote in the round voted `yes` on that meal**. `not_tonight` excludes tonight (stored distinctly, neutral for future learning). | Matches README default ("every participating household member must be willing to eat it"). Simple, explainable, testable. |
| D6 | **Pool modes (MVP)** | `all` · `category` · `tag` · `favorites` · `not-recently` (sort) · `surprise` (random sample of 10) | Covers the README's mode list minus "ingredients on hand" (needs a pantry model — V1.5+). |
| D7 | **Import** | CLI script `scripts/import_legacy.py`: `--dry-run` (default) prints a report; `--apply` inserts. Duplicates flagged, never auto-merged. Categories `Tab 1..8` (renamable). Known takeout names auto-tagged `takeout`. | CLI is testable and reviewable; dry-run first honors "recommend actions rather than silently deleting/merging anything". |
| D8 | **Favorites** | Household-level single list (`favorite(meal_id)`), not per-person | One household, one mental model. Per-person favorites add nothing for MVP. |
| D9 | **History** | A round is history once `status=decided` (has `decided_meal_id`). Meal `times_cooked` / `last_cooked_at` update on decision. | No separate history table needed. "Record what was chosen" = the decided round row. |
| D10 | **Sessions** | Starlette `SessionMiddleware`, secret from env `DD_SECRET` or auto-generated on first run (stored in `data/`), session stores `person_id` | No user auth; device-scoped "who am I". |
| D11 | **Polling, not websockets** | Page refresh / short poll on round pages | A household round has 2–6 people; realtime push is overkill. |

## 4. Legacy spreadsheet state (evidence, audited 2026-08-26)

The import target. Full audit in `reference/README.md`. Facts the import must handle:

- 8 sheets (Sheet1–Sheet8), header row `Roll Result | Dinner | Times Rolled`, up to 20 meal rows. **Sheet position = D8, row = D20.**
- ~155 named meals: Sheet1–7 fully populated; **Sheet8 has only 15** (rows 16–20 empty — import must tolerate holes).
- `Times Rolled` populated on 34 rows (values 1–2, 37 rolls total) — preserve as `meal.legacy_rolls` (historical metadata only).
- 4 recipe URLs (TikTok & damndelicious in standalone cells; cookincanuck & allrecipes embedded in meal names) → `meal.source_url`; import strips embedded URLs from names.
- Takeout entries (Chili's, Taco Bell, McDonald's, Chick Fil A, Panda Express, Raising Cane's, Whataburger, Subway, Los Hermanos, "Order Pizza") → auto-tag `takeout` (they are legitimate dinner answers).
- Catch-alls ("Make do", "Leftovers", "yesterday's chicken") — keep as ordinary meals.
- **One exact duplicate**: "Chicken parm" (Tab 1 & Tab 2) → dedupe report must catch it. Near-duplicates (Chili / Chili Dogs / Chili Dog Casserole / Chili Cheese Dog Tater Tot Casserole) → fuzzy-flag only, human decides.
- Two entries have an `(LC)` suffix (likely "low carb") — preserve name verbatim, no parsing.

## 5. User stories (MVP)

| ID | Story | Acceptance |
|---|---|---|
| US1 | As the admin, I import the spreadsheet once and get a meal library with categories | Import report shows counts; meals appear in library; `Chicken parm` flagged duplicate |
| US2 | As the admin, I add/edit/archive meals and categories | CRUD works; archived meals vanish from pools, visible in library with filter |
| US3 | As anyone, I start a round by picking a pool mode and get a code | Round created; code shown; pool matches the mode |
| US4 | As a household member, I join by code, identify with my PIN, and vote privately | I vote on cards; no other voter's choices visible to me |
| US5 | As the starter, I close voting and see common ground | Only meals everyone (who voted) said yes to appear |
| US6 | As the starter, I roll the dice or pick a meal | Dinner recorded; history updated; meal counters updated |
| US7 | As anyone, I browse history of past dinners | Decided rounds listed newest-first with meal, date, mode |
| US8 | As anyone, I star favorites and can start a round from favorites only | Favorites mode yields only starred meals |

## 6. Data model (SQLite via SQLAlchemy 2.x declarative)

```
person(id PK, name TEXT UNIQUE NOT NULL, pin TEXT NOT NULL,           -- 4-digit
       is_active BOOL DEFAULT 1, created_at DATETIME)

category(id PK, name TEXT UNIQUE NOT NULL, sort_order INT,            -- "Tab 1".."Tab 8" from import
         legacy_sheet_index INT NULL)                                  -- 1..8 for imported; NULL for user-made

tag(id PK, name TEXT UNIQUE NOT NULL)

meal(id PK, name TEXT NOT NULL, normalized_name TEXT NOT NULL,        -- casefold+collapse for dedupe
     description TEXT, image_url TEXT, source_url TEXT,
     prep_minutes INT NULL, cook_minutes INT NULL, servings INT NULL,
     is_active BOOL DEFAULT 1, archived_at DATETIME NULL,
     last_cooked_at DATETIME NULL, times_cooked INT DEFAULT 0,
     legacy_rolls INT DEFAULT 0, created_at DATETIME, updated_at DATETIME,
     category_id FK -> category)

meal_tag(meal_id FK, tag_id FK, PK(meal_id, tag_id))

favorite(meal_id PK FK)                                                -- household-level (D8)

round(id PK, code TEXT UNIQUE NOT NULL,                                -- WORD-####
      status TEXT NOT NULL,                                            -- lobby|voting|results|decided|expired
      pool_mode TEXT NOT NULL, created_by_person_id FK -> person,
      created_at DATETIME, started_at DATETIME, finished_at DATETIME NULL,
      decided_meal_id FK -> meal NULL)

round_meal(round_id FK, meal_id FK, sort_order INT, PK(round_id, meal_id))

round_participant(round_id FK, person_id FK, joined_at DATETIME, PK(round_id, person_id))

vote(id PK, round_id FK, person_id FK, meal_id FK,
     choice TEXT NOT NULL,                                             -- 'yes'|'not_tonight'|'no' (D4)
     created_at DATETIME, UNIQUE(round_id, person_id, meal_id))        -- one vote per person per meal
```

Notes:
- No hard-no table in MVP; the vote enum is text and extensible (V1.5 adds `hard_no` + per-person constraint table).
- `normalized_name` = `name.casefold()` with whitespace collapsed — the dedupe key.
- Round status flow: `voting → results → decided` (see §9). `expired` is lazy (see §9.5).

## 7. Architecture & app layout

```
dinnerdecider/
├── app/
│   ├── main.py            # FastAPI app, middleware, route registration
│   ├── settings.py        # env-driven (DD_DB_PATH, DD_SECRET, DD_PORT)
│   ├── db.py              # engine, SessionLocal, get_db dependency, init/create-all
│   ├── models.py          # SQLAlchemy models (§6)
│   ├── common_ground.py   # pure functions: survivors computation, pool sampling  ← the testable core
│   ├── codes.py           # round-code generation (WORD-####, collision loop)
│   ├── routes/
│   │   ├── people.py  library.py  rounds.py  history.py
│   ├── templates/         # Jinja2 (base.html, people/, library/, rounds/, history/)
│   └── static/            # app.css, app.js (vanilla; HTMX via CDN or vendored)
├── scripts/import_legacy.py   # spreadsheet import CLI (D7)
├── tests/                 # pytest: unit (common_ground, codes, import) + route smoke (TestClient)
├── pyproject.toml         # uv-managed; deps: fastapi, uvicorn, sqlalchemy, jinja2, python-multipart, openpyxl (import), htmx (vendored)
├── .github/workflows/ci.yml
├── CHARTER.md ROADMAP.md CLAUDE.md REQUESTS.md
├── docs/                  # PLAN-v1-mvp.md, POST-V1.md, DEVLOG.md
└── reference/             # legacy spreadsheet (read-only)
```

- DB file default `data/dinnerdecider.db` (gitignored), overridable via `DD_DB_PATH`.
- Templates are server-rendered; voting interactions are `hx-post` calls to the vote endpoint; the D20 roll is a small vanilla-JS animation over server-provided survivors.
- **No Node, no bundler, no build step.** HTMX vendored as a static file.

## 8. Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Home: start-round CTA, active round link, library/history/people links |
| GET/POST | `/people` · `/people/{id}` | Household profiles CRUD (name, PIN, active) |
| GET | `/library` | Meal library: search, filter by category/tag, archived toggle |
| GET/POST | `/library/new` · `/library/{id}/edit` | Meal create/edit form |
| POST | `/library/{id}/archive` · `/unarchive` | Manual archive (item 10) |
| POST | `/library/{id}/favorite` | Toggle household favorite |
| GET | `/rounds/new` | Pool-mode picker (mode + category/tag selector) |
| POST | `/rounds` | Create round → 303 to `/r/{code}` |
| GET | `/r/{code}` | Round page: join gate → lobby/vote/results/decided by status |
| POST | `/r/{code}/join` | Join as person (name + PIN) → session |
| POST | `/r/{code}/vote` | `{meal_id, choice}` — upsert vote |
| POST | `/r/{code}/close` | Starter closes voting → results (survivors) |
| POST | `/r/{code}/decide` | `{meal_id}` manual, or `{random: true}` roll → decided |
| GET | `/history` | Decided rounds, newest first, filter by month |
| POST | `/rounds/expire-stale` | (ops) mark rounds older than 24h as expired |

## 9. Round lifecycle & common-ground algorithm

### 9.1 Lifecycle

```
[create: pick pool mode] → voting → results → decided
                               ↑ closed manually (starter) or auto (all joined participants voted)
```

- **voting**: participants join (`/join` → PIN → session), see meal cards, vote. Votes are upserts (`UNIQUE(round, person, meal)`).
- **results**: computed survivors shown; per-meal counts NOT shown (just who's in — privacy: no tally, ever, in any client response).
- **decided**: starter picks a card or rolls; `round.decided_meal_id`, `finished_at` set; meal `times_cooked += 1`, `last_cooked_at = now`.

### 9.2 Pool sampling (exact)

- `all`: all `is_active` meals ordered by category/name. If > 40, the picker shows a soft warning ("that's N meals — most households do better with a category or tag") but allows proceeding.
- `category`: `is_active` meals in the chosen category.
- `tag`: `is_active` meals with the chosen tag.
- `favorites`: `is_active` meals in `favorite`.
- `not-recently`: all active meals **sorted** by `last_cooked_at` (NULLs first) — a sort mode, not a filter.
- `surprise`: `random.sample(active_meals, min(10, len))`, seeded per round (reproducible in tests).

### 9.3 Common-ground computation (the core function)

```
participants = [p in round_participants where count(votes by p in round) >= 1]
for meal in round_meals:
    votes_on_meal = votes for meal by participants
    survivors = [meal for meal in round_meals
                 if len(votes_on_meal) == len(participants)
                 and all(v.choice == 'yes' for v in votes_on_meal)]
```

- Participants who joined but never voted do **not** block (starter can close with stragglers).
- `not_tonight` and `no` both exclude tonight; they are stored distinctly (D4/D5).
- Empty survivors → results page shows "no common ground tonight" + guidance (narrow the pool / pick manually / surprise me) — never a dead end.

### 9.4 Random choice (item 7)

D20-flavored roll: server picks uniformly from survivors (`random.choice`); client shows a brief dice animation, then reveals the meal. Manual pick is always available too.

### 9.5 Expiry

Rounds in `voting` older than 24h are treated as `expired` (lazy check on access + a cheap cleanup endpoint). Expired rounds are not shown on home; history only ever shows `decided` rounds.

## 10. Import pipeline (`scripts/import_legacy.py`)

Spec for the implementer — this is a self-contained, heavily testable slice.

- CLI: `--file reference/D20\ Dinner\ Decider.xlsx` (default), `--dry-run` (default), `--apply`, `--json` (machine-readable report).
- Parse (openpyxl, read-only mode):
  - iterate sheets in workbook order (index 1..8 → `Tab N`);
  - skip row 1 (header: A1 == "Roll Result");
  - skip rows where the meal cell (col B) is empty or whitespace;
  - name = col B, strip + collapse internal whitespace (preserve case verbatim); if it contains a URL (`https?://\S+`), split the URL off into `source_url` and clean the remainder;
  - `legacy_rolls` = int(col C) if numeric else 0;
  - `source_url` = a URL in any trailing cell of the row (col D/E) or split off from the name (see above);
  - `normalized_name` = `name.casefold()` + collapse.
- Dedupe report (dry-run and apply):
  - exact: `normalized_name` already seen in-file or already in DB → list both rows, flag `DUPLICATE`;
  - fuzzy: difflib `SequenceMatcher.ratio(normalized) ≥ 0.85` → flag `POSSIBLE_DUPLICATE`;
  - never auto-merge, never auto-skip on fuzzy; exact-dupes already in DB are skipped on `--apply` (reported).
- Takeout auto-tag: curated casefold set `{"chili's","taco bell","mcdonald's","chick fil a","whataburger","subway","los hermanos","panda express","raising cane's","order pizza"}` → create/find tag `takeout`, link.
- Output: per-tab counts, total meals, holes found (e.g. Sheet8), URLs captured, takeout tagged, duplicates/possible-duplicates, skipped-on-reapply.
- `--apply` is idempotent: re-running against a populated DB skips exact normalized-name matches and reports them.

## 11. Milestones & tasks

Each milestone is one or more cycles; each task lists acceptance + verification. Verification commands are run by the lead after the implementer reports — never taken on faith.

### M0 — Foundation (≈1–2 cycles)

| Task | Acceptance |
|---|---|
| T0.1 Scaffold: `pyproject.toml` (uv), `.gitignore`, package layout `app/`, `tests/` | Fresh `uv sync` installs cleanly |
| T0.2 DB layer: `db.py` (engine/session/init), settings | `DD_DB_PATH` respected; DB created on boot |
| T0.3 Models: all §6 tables | Migration-less create-all; models import clean |
| T0.4 App skeleton: `main.py`, session middleware (D10), health route, base template, static | `/health` → 200; session cookie round-trips |
| T0.5 CI: `.github/workflows/ci.yml` (setup-uv, `ruff check .`, `pytest -q`) + ruff config | CI green on push |

Verify: `uv run pytest -q` green · `uv run ruff check .` clean · `uv run uvicorn app.main:app` serves `/` · CI green.

### M1 — Household profiles (≈1–2 cycles)

| Task | Acceptance |
|---|---|
| T1.1 Person CRUD routes + templates (list/add/edit PIN/deactivate) | CRUD from UI; inactive people can't join |
| T1.2 PIN verify → signed session (`person_id`) | Wrong PIN rejected; correct PIN sets session |
| T1.3 "Who am I" header (current person + switch) | Clear identity on every page |

Verify: unit + route tests for CRUD, PIN gate, session persistence.

### M2 — Meal library + import (≈4–5 cycles)

| Task | Acceptance |
|---|---|
| T2.1 Meal CRUD + library UI (list, search, category/tag filter, form, detail) | Full CRUD works |
| T2.2 Archive/unarchive + favorite toggle (US2, US8 partial) | Archived hidden from pools; favorite flag works |
| T2.3 Import CLI per §10 (parser, normalize, dedupe, takeout tag, dry-run/apply) | See §10 acceptance |
| T2.4 Import tests against `reference/` file (structural invariants, not exact-count brittleness) | 8 tabs; ≥150 meals; 4 URLs; `Chicken parm` flagged dup; ≥10 takeout-tagged; re-run idempotent |

Verify: real-file import dry-run shows sane report; `--apply` → 155 meals, 8 categories, dupes listed; re-`--apply` skips cleanly.

### M3 — Rounds & voting (≈6–8 cycles — the core loop)

| Task | Acceptance |
|---|---|
| T3.1 Round creation: picker (D6 modes) → round with code (D3) | Code unique; pool matches mode |
| T3.2 Join flow: code → person → PIN → participant (US4) | Non-participant blocked from voting |
| T3.3 Vote UI: meal cards (name, category, tags, image if any, last cooked) + yes/not-tonight/no | One-tap voting; per-card state shown |
| T3.4 Vote endpoint upsert + **privacy** (no tallies to clients until closed) | Test: client response during voting contains zero other people's votes |
| T3.5 Close voting (manual + auto) → survivors via §9.3 | Correct survivors for table-driven cases |
| T3.6 Decide: manual pick + D20 roll (US6) | Recording works; counters update |
| T3.7 Pool modes wired end-to-end | Each mode yields the right pool |

Verify: **two-browser walkthrough** over LAN (start → join ×2 → vote → close → survivors → roll → history entry); empty-survivors case shows graceful path; privacy test green.

### M4 — History & favorites (≈2 cycles)

| Task | Acceptance |
|---|---|
| T4.1 History page (decided rounds, newest first, month filter) (US7) | Correct rows incl. meal/date/mode |
| T4.2 Meal counters (`times_cooked`, `last_cooked_at`) on library | Update after decisions |
| T4.3 Empty/error states (no meals, no rounds, no survivors, unknown code) | No 500s; friendly messages |

Verify: history correct after multi-round test; counters correct; 404/error paths tested.

### M5 — Hardening, polish, docs (≈2–3 cycles)

| Task | Acceptance |
|---|---|
| T5.1 Responsive pass — phones are the critical path (vote screen) | Vote screen usable on 360px-wide viewport |
| T5.2 README "Run it" (uv sync → uvicorn → import), backup note (copy the .db), troubleshooting | Fresh clone → running in 3 commands |
| T5.3 Final verification: full suite + ruff + fresh-checkout run + full walkthrough checklist | DoD (§15) all checked |
| T5.4 (optional) seed/demo script | Not required for DoD |

## 12. Testing & CI strategy

- **Unit (pytest)**: `common_ground` survivors (table-driven: all-yes, one no, one not-tonight, skipped participant, empty), pool sampling (surprise determinism via seed, caps), `codes` (format regex + uniqueness), import parser (normalize/dedupe/takeout).
- **Integration**: import against the real `reference/` file (structural invariants); full round flow via FastAPI `TestClient` (US1–US8 smoke).
- **Privacy test** (M3): assert no vote data other than the caller's own appears in any voting-phase response.
- **CI**: GitHub Actions — `astral-sh/setup-uv`, `uv sync`, `ruff check .`, `pytest -q`, on push + PR.
- Rule: **the lead re-runs everything; a green self-report is never accepted.**

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Common ground too often empty (family with one picky eater + hard constraints) | Graceful "no common ground" path; manual pick always available; pool modes to narrow; looser rules are a designed V1.5 feature — tracked, not improvised |
| 155-meal pool too big to vote on | Pool >40 warning; category/tag/favorites/surprise modes front-and-center |
| Vote privacy leaks via timing/results | Results strictly server-gated until close; no tally in any response; cookie httponly |
| Import mess (dupes, casing, holes) | Dry-run report, exact+fuzzy dedupe flags, human decides, idempotent re-run |
| Scope creep toward AI | Hard non-goals + stop criteria + REQUESTS channel for ideas |
| Household doesn't adopt it | Success criterion is real usage; stop criteria explicit; MVP is intentionally small |

## 14. Open questions (resolve through use, not upfront design — per README)

| Question | MVP default | When to revisit |
|---|---|---|
| How many meals in a round? | Starter's choice; soft warning >40 | After real rounds |
| Vote whole pool or progressively narrow? | Whole pool | After real rounds |
| Does `not_tonight` count as rejection long-term? | Neutral (stored distinctly; no learning in MVP) | V1.5 learning design |
| Hard-no auto-hide? | Out of MVP (D4) | V1.5 |
| Archived meals re-offered? | Manual unarchive only | V1.5 stale suggestions |
| Random or manual default? | Both, always | After real rounds |
| How much dice ritual to keep? | D20-flavored roll on survivors | After real rounds |
| New-recipe probation pool? | N/A (no ingestion in MVP) | V2 with AI discovery |

## 15. Definition of done & stop criteria

DoD: **CHARTER.md §"Definition of done"** — all five household capabilities working from household devices, plus the README success criterion. Stop criteria: **CHARTER.md §"Stop criteria"** — budget (25 cycles), non-adoption after a fair trial, chronically empty common ground, or Charlie's call.

**Approval gate:** this plan and the charter are pending Charlie's sign-off. M0 does not start until approval.
