# Same Page

Same Page is a platform for a household or a friend group to keep a shared database of options and vote on them privately until everyone agrees. Full architecture: [`docs/PLAN-v2-samepage.md`](docs/PLAN-v2-samepage.md).

## What's actually built right now

- **Accounts and groups.** Sign in with Google (no passwords in this app). Any account can create a group and becomes its owner; the owner can add other admins.
- **A shared meal library.** A group's admin creates a collection and adds meals to it. Meals can be browsed, searched, filtered, tagged, added, edited, and archived.
- **The voting engine.** A host starts a session against a collection, sets targets (e.g. 3 dinners), and shares a code. People join by code from their phones — no account needed. The app serves a batch of options one at a time; each person votes yes/no privately. Options everyone said yes to are kept automatically; majority options are offered to the host to accept. The host runs more batches until the plan is done, then finishes — and the per-person votes are deleted, leaving only the aggregate outcome. Nobody ever sees who voted which way.
- **Reporting.** Per-collection reject rates by meal and by tag, and a "not offered lately" list, built from the voting outcomes.
- **A JSON API.** A group owner can mint a per-group token to let external AI tools read and write that group's library and read its reports (`/api/v1`, Bearer auth). No AI runs inside the app; sessions and votes are not exposed over the API.
- **Installable (PWA).** Add it to a phone's home screen; it runs full-screen.

The meal library is the first thing built on the voting mechanic. It's meant to work for anything a group needs to decide together: what to do this weekend, which game to play, where to eat.

## Docs

- [`CHARTER.md`](CHARTER.md) — scope, non-goals, locked decisions (partially superseded — see its banner)
- [`ROADMAP.md`](ROADMAP.md) — milestone status
- [`docs/PLAN-v2-samepage.md`](docs/PLAN-v2-samepage.md) — current architecture: accounts, groups, collections, how voting will work
- [`docs/DEVLOG.md`](docs/DEVLOG.md) — what actually shipped, in order

## Run it locally

```
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app
```

Then, in the browser: sign in with Google, create a group, and create a meal collection in it (`Collections → + New collection`) — a new deployment starts with an empty database, so the collection starts empty and meals are added from the library's "+ Add a meal" button.
