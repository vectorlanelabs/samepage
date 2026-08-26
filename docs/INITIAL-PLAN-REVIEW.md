# Initial Plan Review

The current charter and v1 plan are coherent and close to implementation-ready, but several issues should be resolved before M0. The product direction is sound; the concerns below are primarily about ambiguity, data durability, and mismatches between the operative plan and supporting docs.

## Required before implementation

### 1. Freeze the participant roster before voting

The current unanimity rules are inconsistent:

- D5 says meals are kept when every participant who voted said yes.
- Manual close says unvoted = no.
- The algorithm defines voters as participants who voted at least once in the batch.
- Auto-close can occur as soon as all current participants finish, which could happen before intended household members have joined.

Add a lobby/roster phase:

1. Create the planning session.
2. Household members join.
3. Starter explicitly starts voting.
4. Participant roster freezes for the session.
5. First batch is created.
6. Auto-close requires every roster member to vote on every meal.
7. Manual close treats missing votes as `no`.

Unanimity should then be defined simply:

> A meal qualifies only if every required participant has an explicit `yes` vote.

Late joining after voting starts should be disallowed in v1.

### 2. Add database migrations in M0

The app is intended to hold durable family data and the schema is expected to grow substantially in v1.5/v2. `create_all()` alone is not sufficient for that lifecycle.

Add Alembic in M0 and treat all schema changes after initial creation as migrations.

### 3. Make SQLite backups consistency-safe

The deployment plan calls for daily database backups. If SQLite runs in WAL mode, ordinary filesystem copying of the live `.db` file should not be treated as a reliable backup procedure.

Use a supported SQLite backup mechanism such as:

- SQLite backup API
- `.backup`
- `VACUUM INTO`

M5 verification should include restoring a backup into a fresh instance and confirming the application can read it.

### 4. Resolve the lunch-track mismatch

Lunch is currently a first-class v1 workflow, but the seed contains only `dinner` meals. A fresh installation therefore has no successful lunch path without immediate manual data work.

Choose one before implementation:

- Curate a reasonable subset of existing meals as `lunch` / `both` and make that part of the seed; or
- Remove lunch-track support from v1 and add it later when there is a real lunch library.

Do not leave an intentionally empty core track as the default shipped state.

### 5. Define administration and authorization

The charter says one household member administers the app, but the data model does not distinguish administrators from ordinary participants.

Define which actions require admin privileges, at minimum:

- managing household members
- changing PINs
- archiving/unarchiving meals
- any future destructive or maintenance operations

Recommended model addition:

- `Person.is_admin`

Also store PINs as hashes rather than plaintext.

Because the app is internet-facing, explicitly require secure cookie settings (`Secure`, `HttpOnly`, appropriate `SameSite`) and CSRF/origin protection for state-changing requests.

### 6. Strengthen the vote-privacy invariant

The current wording protects individual votes only while the batch is open. The product principle is stronger than that.

Use this invariant instead:

> Individual household-member votes are never exposed in the normal UI, before or after batch closure.

After a batch closes, normal users should see only aggregate outcome information such as:

- meals that reached common ground
- no-match state
- meals ultimately kept

Raw votes remain server-side for future preference learning and diagnostics.

## Documentation cleanup

### 7. Remove stale product descriptions from the active README

The README clearly says the charter and plan are operative, but its original concept section still describes behaviors that no longer match v1, including:

- spreadsheet import
- `yes / not tonight / no`
- random final selection
- recording one selected dinner rather than building a weekly plan

Move the original concept into `docs/ORIGINAL-CONCEPT.md` or clearly separate it from current behavior. The README should primarily describe the product actually being built.

### 8. Fix deployment contradictions in post-v1 docs

`POST-V1.md` and the roadmap refer to hosted deployment as a later possibility even though v1 is explicitly VPS-hosted from day one.

Replace that future item with something like:

- multi-household hosting
- real accounts
- public/self-service deployment

Also avoid calling the seed-generation path an end-user “import pipeline”; there is no import feature in v1.

### 9. Restore recipe view and printing to the roadmap

The original concept explicitly calls for a clean cooking view and first-class printing, but those requirements are not attached to the post-v1 recipe-intake plan.

When recipe intake becomes real, include:

- structured recipe record
- original source preserved
- clean cooking view
- print-friendly recipe layout / stylesheet
- household notes and modifications

Recipe ingestion without the corresponding recipe-use experience leaves the feature incomplete.

## Recommended simplifications and safeguards

### 10. Do not expose batch size as a routine setup choice in v1

Pick a default, preferably 15, and change it later based on real household use. Batch size is an implementation tuning parameter, not an important household planning decision.

### 11. Make state transitions idempotent

At minimum, make these operations safe against double-submit and concurrent requests:

- close batch
- record keeps
- advance to next batch
- finish session

A duplicate request must not increment `times_kept` twice or advance the session twice.

### 12. Deactivate people instead of deleting historical participants

Once a person has vote/session history, removal should preserve referential integrity and historical records. Use active/inactive state rather than destructive deletion.

## Overall assessment

The core sequencing is strong:

- **v1:** prove private common-ground voting reduces meal-planning friction.
- **v1.5:** improve rotation, cleanup, and library quality using real usage history.
- **v2:** add recipe intake, preference inference, and AI-assisted discovery only after meaningful household data exists.

The decision to defer AI until real vote/keep history exists is appropriate. The stop criterion for revisiting unanimous consensus if sessions consistently stall is also sound.

Resolve the participant-roster logic, migrations/backups, lunch scope, administration rules, and privacy wording before approving M0. After those changes, implementation should begin rather than extending planning further.
