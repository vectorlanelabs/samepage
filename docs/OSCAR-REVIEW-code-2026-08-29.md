# Oscar's Review — SamePage shipped code (2026-08-29)

> Reviewer: Oscar persona (`ai-grouch-claude` skill), run on the Fable model, Full codebase mode.
> Target: the actual shipped, working code — `app/`, `tests/`, `alembic/`, `scripts/` — as it stood on
> 2026-08-29 after that day's tenant-isolation hotfixes (library scoping, home page scoping, 401 redirect,
> `next` param). This is a review of shipped code, not the architecture plan — see
> `docs/OSCAR-REVIEW-plan-2026-08-29.md` for that separate review.
>
> Saved verbatim (formatting cleanup only). Status of each finding as of the time of writing: **not yet
> acted on** — cross-reference `docs/DEVLOG.md` for what happens to these findings next.

---

Scope actually inspected: all of `app/` (routes, auth, security, credentials, settings, db, models, main), all 9 templates, `scripts/seed.py`, all 5 alembic migrations + `env.py`, all 15 test files, plus empirical probes run against the real app (`uv run pytest`, ruff, and a temporary probe suite exercising the live routes — probe file removed afterwards). Findings below marked **[verified]** were reproduced by running code, not inferred.

## Executive verdict

**Needs changes.** The tenant-isolation fixes that landed today are genuinely correct — I attacked `_get_meal_collection`, `_get_owned_item_or_404`, the home-page scoping, and `_safe_next` and they held. But the codebase still contains one reproducible 500 on the flagship page (`/library` crashes on any item lacking a `meal_detail` row — **[verified]**), a tenant-privacy inconsistency in `groups.py` that repeats today's bug class in miniature (group-existence oracle via 403-vs-404), and a real design hole: an account attached to more than one group silently gets exactly one library with no way to reach the others. The three fixes from today shipped with **zero tests** for the `next`-redirect machinery, and the mutation routes have no cross-tenant regression tests — the exact green-tests-hide-real-bugs failure mode the owner is angry about is still open on the write path. Coverage limitation: I did not execute the alembic downgrade paths (read only), and I did not test behind an actual reverse proxy (the Origin/Host comparison's proxy behavior is asserted from code, not deployment).

## Blocking issues

**1. `/library` 500s on any item without a `meal_detail` row**
- severity: blocking
- evidence: `app/routes/library.py:349-350` — `item_details.get(item.id, MealDetail())`. `item_details` always contains a key for every item (line 336 stores the result of `_item_meal_detail`, which can be `None`), so `dict.get(key, default)` returns **None, not the default** — then `.type` raises `AttributeError`. **[verified: reproduced AttributeError → 500 with a probe test]**
- why it breaks: the schema allows detail-less items (`meal_detail` is an optional 1:1; `update_meal` line 595 and `cycle_type` line 639 both defensively create a missing detail, proving the code itself expects them to exist), and any future non-meal collection kind, partial insert, or manual DB fix bricks the entire library page for that group. The `MealDetail()` fallback is triple slop: it's dead (never returned by `.get`), and even if reached, a freshly constructed `MealDetail().type` is `None` at instantiation (column defaults apply at flush), which only works because of the trailing `or "dinner"`. Three layers of defense, and the one that runs is none of them.
- what would change my mind: a NOT NULL-enforced invariant (e.g. FK constraint guaranteeing 1:1 at the DB level) plus a migration proving no detail-less item can exist. Neither is present.

**2. Group-existence oracle: `require_group_admin` returns 403 for real groups, 404 for missing ones**
- severity: blocking (it's today's proven bug class — cross-tenant information disclosure)
- evidence: `app/auth.py:45-53` — 404 if `group is None`, 403 if not admin. `library.py`'s docstring (lines 8-10) states the platform rule explicitly: "A nonexistent-or-not-yours item returns 404, never 403, so browsing doesn't reveal that another group's item exists." `groups.py` violates that same rule one file over, and `tests/test_groups.py::test_group_detail_requires_owner_or_admin` **asserts the leak as correct behavior** (expects 403).
- why it breaks: any signed-in account can walk `/groups/1..N` and enumerate exactly which group ids exist on the deployment (403) vs not (404), and via response timing/shape confirm platform tenancy structure. Small leak, but it's the identical philosophy failure that produced today's two incidents, and the test suite is snapshotting it.
- what would change my mind: an explicit, documented decision that group-id existence is non-sensitive. Given the owner just got burned twice by "harmless" global visibility, that decision should be his, not the code's default.

## Major concerns

**3. Multi-group accounts get an arbitrary single library; the rest are unreachable**
- severity: major
- evidence: `library.py:76-93` `_get_meal_collection` — `order_by(Collection.id).limit(1)`. **[verified: probe with an account owning group A and admining group B showed only A's items; B's library is inaccessible from the UI, ever]**. Meanwhile `_get_owned_item_or_404` accepts items from *any* owned collection, so a direct URL to B's item renders fine — but its "← Back to library" link takes you to A's library, and `create_meal` always inserts into A.
- impact: the product's core premise is multi-group membership ("families/friend groups"); the moment the second group exists, browse/create silently bind to whichever collection has the lowest id. Add-admin works today, so this state is reachable in production right now.
- suggested fix: either scope the library under `/groups/{id}/library` (the honest URL structure for the data model you actually built) or add an explicit collection picker. The current code is a single-tenant UI wearing a multi-tenant schema.

**4. `_safe_next` has the classic backslash bypass — saved only by accident**
- severity: major (hardening, not currently exploitable)
- evidence: `app/routes/auth.py:25-30`. `next=/\evil.com` passes the guard (starts with `/`, not `//`); browsers normalize `\` to `/` in locations, yielding `//evil.com`. **[verified: the guard passes it — the response Location came out as `/%5Cevil.com` only because Starlette's `RedirectResponse` percent-encodes the backslash]**. The guard's correctness currently depends on an undocumented encoding behavior of the framework's redirect class, which the code neither tests nor mentions.
- impact: any future refactor that builds the `Location` header differently (template link, `HTMLResponse` meta-refresh, manual header) silently reopens an open redirect.
- suggested fix: reject `\` explicitly (`"\\" not in value`) or parse with `urlparse` and require empty scheme/netloc. Two lines. And add the test — there are **no tests at all** for `_safe_next`, `?next=`, or the 401→login redirect handler; today's hotfixes #3 and #4 shipped exactly the way the two leaks did: untested.

**5. No cross-tenant regression tests on any mutation route**
- severity: major (test gap in the proven-real bug class)
- evidence: `tests/test_library.py` — tenant-isolation tests exist only for GET `/library` and GET `/library/{id}` (lines 202-218, 278-286). `POST /library/{id}` (update), `/archive`, `/unarchive`, `/cycle-type` have **zero** tests attempting another group's item. The protection exists in code (`_get_owned_item_or_404`), but nothing pins it; a refactor that drops the guard from one POST route ships green.
- suggested fix: one parametrized test hitting every item-addressed mutation route with another tenant's item id, asserting 404 and no DB change.

**6. Library page queries scale with the whole platform, not the tenant**
- severity: major (data-access review hit: filter in the wrong layer + N+1)
- evidence: `library.py:338-340` — `select(ItemTag.item_id, Tag.name).join(Tag)` loads **every item-tag link on the entire deployment** into memory on every library render, then filters via dict lookup. And lines 335-336 run `_item_meal_detail` once per item — an N+1 of ~155 queries per page view.
- impact: not a leak (rows are only used for own items), but page cost grows with total platform data — the multi-tenant version of a landmine. The N+1 is the difference between 3 queries and 158 per view.
- suggested fix: join `ItemTag` through `Item.collection_id == collection.id`, and fetch details with one `select(MealDetail).where(MealDetail.item_id.in_(...))`.

**7. `is_active` is a dead column shadowing `archived_at`**
- severity: major (schema slop with a bite)
- evidence: `models.py:98` + grep: `is_active=True` is written in `library.py:531` and `seed.py:150` and **never read or set to False anywhere**. All archive semantics run on `archived_at`. Two columns claim the same invariant; one is a lie.
- impact: the M3 voting engine will have to choose which flag means "in the roster" — someone will pick the wrong one, and there is no test to catch it because nothing exercises `is_active` at all. Same story, smaller stakes: `times_offered` is written only by the seed and never read; `Item.description` is hardwired `None` at both creation sites; `Category` (model + migration + 8 seeded rows per group) has zero route/template consumers — categorization data goes in and never comes out.
- suggested fix: drop `is_active` in the next migration (archived_at is the real mechanism), or define it and enforce it. Decide whether Category is M3 material or spreadsheet nostalgia; if M3, say so in a comment tied to the plan; if not, drop it.

**8. `/logout` is unreachable from the UI**
- severity: major
- evidence: `app/routes/auth.py:127` defines POST `/logout`; grep over `app/templates/` finds zero references. `base.html` has no sign-out control, no account indicator, and shows the identical nav to signed-in and signed-out users.
- impact: on a shared/family device — this product's literal use case — nobody can sign out without hand-crafting a POST (and a bare `<a href>` wouldn't work anyway: it's POST-only behind the origin check). The route is tested green (`test_logout_clears_session`) while being dead in the product. That is precisely the "tests pass, app wrong" pattern under audit.

## Minor concerns and nits

Real minor issues:
- **`verify_password` docstring lies**: "never raises" (`credentials.py:29-31`), but odd-length hex in the salt/hash groups makes `bytes.fromhex` raise `ValueError` — the regex `[0-9a-f]+` doesn't enforce even length, and `tests/test_credentials.py`'s malformed list happens to only use even-length hex. Latent (only self-generated hashes are stored today), but the comment promises a guarantee the code doesn't hold.
- **Group-create error page loses the user's groups**: POST `/groups` with blank name re-renders `groups.html` without the `groups` context key → the page shows "No groups yet. Create one above." to a user who has groups. **[verified: 400, existing group absent from response]**. Missing the field entirely yields a raw 422 JSON in a browser flow.
- **401 redirect drops the query string**: `main.py:85` uses `request.url.path` — `/library?status=archived` post-login lands on `/library`. **[verified]**
- **Signup flow drops `next`**: user hits 401 → `/login?next=X` → clicks "Sign up" → after signup, redirected to `/`, destination lost.
- **`add_admin`/`remove_admin` owner-only failures say "Admin required"** (`groups.py:130,191`) — the caller *is* an admin; the message should say owner. Also `add_admin` is an account-email existence oracle for any group owner ("No account with that email exists") — probably acceptable for this product, but it's a decision, not an accident, so record it.
- **`order_by(Item.name)` is case-sensitive** under SQLite's BINARY collation — "Ziti" sorts before "bacon and eggs". `normalized_name` exists for exactly this and isn't used for ordering.
- **Seed loader's within-run dedupe gap**: `seed.py:83-99` builds `existing_normalized` once and never adds newly created names — duplicate names inside one seed file both insert, contradicting the docstring's "any item whose normalized name already exists … is skipped". Also the category-without-index `continue` (line 117) skips a whole meal without incrementing `skipped`, so the summary line undercounts.
- **`tests/test_origin_check.py:150-163`** still posts `{"name": "Ada", "pin": "1234"}` to `/login` — PIN-era payloads two migrations stale. Passes only because the middleware rejects before the body is parsed.
- **`tests/test_session.py` docstring**: "M0 has no session-writing route (auth arrives in M1)" — auth has existed for a while; the justification for the probe-app approach is now false even though the test itself is still fine.

Taste nits: `logger = logging.getLogger("dinnerdecider")` (`main.py:28`) — stale branding, and nothing in the app ever logs to it except the chmod warning; `--dd-*` CSS variables throughout (49 in app.css) are pre-rename residue; `can_edit = True` hardcoded in `library_page` with the template still carrying full `{% if can_edit %}`/`{% else %}` branches — vestigial Person-era admin gating kept as ballast; `no_collection: True` passed to a template that never references it, so the no-collection empty state misleadingly reads "No meals match these filters"; htmx is vendored and loaded on every page with zero `hx-` attributes anywhere; `recipe_view` grafts `item.recipe_text = ...` onto the ORM object "for template compat" instead of passing `detail` to the template.

## What the code gets right

Plenty, and I'll say it plainly because I went in expecting worse from the M0 lineage:

- **Today's two leak fixes are correct.** `_get_meal_collection` puts the account condition in the outer-join ON clause and the WHERE, so it cannot return another tenant's collection; `_get_owned_item_or_404` checks ownership through collection→group→owner/admin and deliberately 404s; the home page's early-return for anonymous visitors plus `own_group_ids` scoping is right, and both have real route-level regression tests with honest docstrings naming the original bug. **[verified with multi-tenant probes]**
- **The origin-check middleware is genuinely good**: fail-closed on absent Origin, exact-boundary `/mcp` matching (`/mcpfoo` correctly not exempt), and `test_origin_check.py` is a model test file — it proves the handler *didn't run* on rejection via the mutations list, not just the status code.
- **Password handling is boring and right**: stdlib PBKDF2 at 600k iterations, per-account salt, constant-time compare, strict-parse fail-closed (modulo the odd-hex nit), single generic login error for both unknown-email and wrong-password.
- **`_safe_next` and the 401 handler survived direct attack attempts** — backslash, double-encoding, and Accept-header probing all failed to produce an actual exploit in the current framework stack.
- The migration chain is coherent, `0004`/`0005` drop the dead Person/Session-era tables with honest reasons and real downgrade paths, `env.py` re-reads settings correctly so `_run_migrations`'s env juggling actually works, and `test_fresh_boot` proves a from-scratch boot. The file-permission hygiene (0600 DB, 0700 data dir, O_EXCL key creation) is more careful than most hobby deployments.

Initial suspicion partially overturned: the *newest* code (M2a/M2b auth and tenancy core) is the healthiest layer. The rot is concentrated in what M2b failed to remove (dead columns, dead nav concepts, PIN-era test payloads) and in the library page's rendering path, which is the oldest surviving M2 code lightly rewrapped.

## Best next moves

1. Fix the `item_details.get(...)` crash (blocking #1) — it's a three-line fix (`detail = item_details[item.id]; type = detail.type if detail else "dinner"`) plus the regression test I already wrote the shape of.
2. Decide the 403-vs-404 policy for groups (blocking #2) and align `require_group_admin` + tests with the library's own stated rule.
3. Add the missing test band: cross-tenant POSTs on every item mutation route, `_safe_next` (including `/\evil.com`), and the 401→login redirect. This is the cheap insurance against the exact failure mode that burned you twice.
4. Kill the dead weight in one slice: `is_active`, `no_collection`, `can_edit` branching, htmx include, PIN payloads in tests, `dinnerdecider` logger. Each is small; together they're the difference between a codebase you trust and one you audit by hand.
5. Put a sign-out control in `base.html` and decide the multi-group library UX before M3 builds on the single-collection assumption.

## Codebase review addendum

- **Systemic risks**: (1) *Tenancy enforced per-route, not structurally* — every route re-derives scoping by hand, and history shows a route can simply forget; there is no query-layer or dependency-layer guarantee (e.g. a `require_owned_item` FastAPI dependency, or scoped query helpers as the only way to touch `Item`). Until scoping is structural, every new route is a fresh chance at leak #3. (2) *Tests validate handlers, not the product* — dead routes test green (`/logout`), leaky semantics test green (403 oracle), and the newest security code (`next` handling) has no tests; the suite measures "does the code do what the code does". (3) *Schema carries speculative and dead capacity* (`Collection.kind` with one kind, `Category` with no consumer, `is_active`, `times_offered`, `description`) — each is a decision M3 will trip over.
- **Hotspots worth manual inspection**: `app/routes/library.py` (largest file, oldest surviving logic, both the crash and the N+1 live here — it's rewrapped M2 code and it shows); `app/auth.py` guards whenever M3 adds member-vs-admin distinctions (the current owner/admin binary won't survive voting members); the `_ORIGIN_EXEMPT_PREFIXES` list the moment `/api/` routes actually exist — exempting them is only safe while Bearer auth is real and enforced on every one.
- **Repeated anti-patterns**: rename residue as a lifestyle (`dd-` CSS vars, `dinnerdecider` logger, "meal"/"track" naming atop the generic Item schema, `"meal": item  # keep template var name for compatibility` in two routes); defensive fallbacks stacked where an invariant should be (the triple-fallback in the crashing line; `update_meal`/`cycle_type` re-creating missing details instead of the schema guaranteeing them); error re-renders that rebuild partial context (groups.html losing the group list).
- **Areas healthier than expected**: `app/security.py` + its tests, `app/credentials.py`, the migration chain and boot-time migration story, and `scripts/seed.py`'s idempotency-with-household-edits-win semantics (`test_seed_skips_existing_household_edit` is exactly the right test). `tests/conftest.py` is clean and its `post` fixture (same-origin by default) is the right way to live with a fail-closed CSRF middleware.

Verification for this review: `uv run ruff check .` — clean; `uv run pytest -q` — 94 passed on the untouched tree; probe suite ran 6 targeted attack/edge tests against the live app (1 confirmed crash, 5 confirmed-safe behaviors) and was deleted afterwards. No project files were modified.
