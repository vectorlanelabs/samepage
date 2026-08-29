# Same Page

Same Page is a platform for a household or a friend group to keep a shared database of options and vote on them privately until everyone agrees. Full architecture: [`docs/PLAN-v2-samepage.md`](docs/PLAN-v2-samepage.md).

## What's actually built right now

- **Accounts and groups.** Sign in with Google (no passwords in this app). Any account can create a group and becomes its owner; the owner can add other admins.
- **A shared meal library.** A group's admin creates a collection and adds meals to it. Meals can be browsed, searched, filtered, tagged, added, edited, and archived.
- **No voting yet.** The plan calls for batches of options and private yes/no votes until a group agrees, but that part isn't built. That's the next milestone.

## The voting mechanic (designed, not built)

A group sets a target: how many meals for the week, how many weekend options to settle on, whatever fits the collection. The app serves a batch of options, the same list to everyone. Each person votes yes or no, privately, and nobody sees anyone else's vote, before or after. Options everyone said yes to are kept automatically; options with a majority get shown to the host, who can accept them too. The app serves another batch and repeats until the target is met.

The meal library is the first thing built on this mechanic. It's meant to work for anything a group needs to decide together: what to do this weekend, which game to play, where to eat.

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
