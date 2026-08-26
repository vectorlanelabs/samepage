# Dinner Decider

A household meal-decision app that learns what everyone will actually eat.

## The problem

Our current system is a spreadsheet with **8 tabs and 20 dinner options per tab**. To pick dinner, we roll a D8 and a D20 and use the resulting indexed meal.

That works for randomness, but not consensus.

After a meal is selected, everyone still gets a yes/no vote. One family member has food-related sensitivities and preferences that can make a randomly selected meal a nonstarter. The result is that the dice narrow the list, but they do not really solve the decision problem.

Dinner Decider should replace the spreadsheet-and-dice ritual with a lightweight shared decision system that gets better as the household uses it.

## Core idea

Combine a household meal library with a **Common Ground**-style private voting mechanic.

1. Start with a set of candidate meals.
2. Each household member independently marks meals they would be willing to eat.
3. Do not expose individual votes while voting is happening.
4. Show only meals that have sufficient household agreement.
5. Pick randomly from the surviving options, or let the household choose from them.
6. Learn from repeated voting behavior over time.

The goal is not to optimize nutrition, generate meal plans, or turn dinner into project management.

The goal is simply:

> **What can we make for dinner that everyone is actually willing to eat?**

## Key product principles

### Consensus before randomness

Randomness is useful only after obviously unacceptable options have been removed.

The current D8/D20 mechanic is fun and should not necessarily disappear. A digital equivalent can still provide the final selection, but it should roll among meals that survived the household vote.

### Private voting

One person's answer should not influence everyone else's.

Each household member sees the same candidate meals and independently answers. The app reveals the common-ground results, not a running tally of who rejected what.

This avoids negotiations such as "Well, if nobody else wants it..." and keeps the process low-friction.

### Preferences are learned, not assumed

The app should remember actual behavior:

- meals a person regularly accepts
- meals a person regularly rejects
- meals the entire household regularly rejects
- meals that are sometimes acceptable but context-dependent
- meals that used to work but appear to have fallen out of favor

It should not overreact to a single no vote.

### Respect hard constraints

Some meal preferences are stronger than ordinary taste.

The system should allow a household member to distinguish between concepts such as:

- **Yes** — willing to eat this
- **Not tonight** — normally acceptable, just not wanted now
- **No** — generally not interested
- **Never / hard no** — do not suggest this to this person

The exact labels can change, but the data model should distinguish permanent constraints from temporary mood.

### Quietly improve the library

Meals that everyone repeatedly rejects should eventually be surfaced for cleanup rather than cluttering the candidate pool forever.

Example:

> Nobody has voted yes for Chicken Alfredo in the last 9 times it appeared. Retire it?

Purging should always be reversible or archived rather than destructive.

## Household flow

### Start a dinner round

One person starts a round and chooses how broad the candidate pool should be.

Possible modes:

- all active meals
- one category / existing spreadsheet tab
- quick meals
- meals using ingredients on hand
- favorites
- meals not eaten recently
- surprise me

The app creates a shared voting session accessible from the devices or browsers available around the house.

### Vote

Each person sees meal cards containing enough information to make a decision quickly:

- meal name
- optional photo
- short description
- tags
- approximate prep/cook time
- last time eaten

Voting should be extremely fast. This is not Tinder for casseroles; nobody needs a 14-step onboarding ceremony to reject meatloaf.

### Find common ground

Once everyone has voted, show the meals meeting the current agreement rule.

Default rule:

- every participating household member must be willing to eat it

Possible future rules:

- everyone yes
- no hard-no votes and at least N yes votes
- parents choose among children's accepted meals
- allow one abstention

### Decide

From the common-ground pool:

- choose manually
- randomize
- digital D8/D20-style roll
- weighted random choice favoring meals not eaten recently

Then mark the selected meal as tonight's dinner.

## Meal library

Dinner Decider should own a durable household meal library rather than just a flat voting list.

A meal can contain:

- name
- aliases
- category / categories
- description
- image
- recipe source
- recipe text
- ingredients
- instructions
- prep time
- cook time
- servings
- tags
- notes
- household-specific modifications
- active / archived state
- last cooked date
- times cooked
- per-person preference history
- household voting history

## Existing spreadsheet migration

An early requirement should be easy ingestion of the existing spreadsheet.

Current source structure:

- 8 tabs
- 20 meal entries per tab
- tab number maps to D8 result
- row number maps to D20 result

Import should preserve the source tab/category information so the existing organization and dice ritual can be recreated digitally if desired.

A CSV/XLSX import flow should be sufficient initially.

## Recipe intake

Adding a meal should not require manually formatting a recipe.

Possible intake paths:

### URL import

Paste a recipe URL. Dinner Decider extracts:

- title
- image
- ingredients
- instructions
- servings
- timing

The app stores a clean household copy plus the original source URL.

### Paste recipe

Paste arbitrary recipe text and normalize it into the same structure.

### Manual meal

A meal does not need a formal recipe. "Tacos," "frozen pizza," or "grilled cheese and tomato soup" are perfectly valid dinner options.

### Photo / document intake — later

Potential future support for importing recipes from images, screenshots, PDFs, or scanned recipe cards.

## Recipe view and printing

Once ingested, recipes should have a clean, distraction-free view optimized for cooking.

Important characteristics:

- large readable ingredients and steps
- no life story before the ingredient list
- keep screen awake while cooking, where the platform allows it
- adjustable serving size later
- household notes and substitutions
- printable layout that fits cleanly on paper

Printing should be a first-class feature, not an accidental browser printout.

## Preference learning

The app should accumulate evidence rather than pretending it understands a person's tastes after three clicks.

Useful signals include:

- yes / no / not-tonight / hard-no votes
- whether the selected meal was actually cooked
- repeat acceptance over time
- repeated household-wide rejection
- categories, ingredients, cuisines, textures, and preparation styles associated with accepted/rejected meals
- recency: rejecting something eaten yesterday means something different from rejecting it six months later

Preference history should remain inspectable and correctable.

## Library cleanup

Periodically identify stale meals:

- repeatedly rejected by everyone
- never selected despite many appearances
- duplicates
- missing enough information to be useful

Recommend actions rather than silently deleting anything:

- keep
- archive
- merge
- update recipe

## AI layer

AI is useful here only if it improves the meal pool. It should not become the product's personality.

### Recipe discovery

Based on accumulated household preferences, suggest meals the household has a meaningful chance of accepting.

A useful suggestion should explain itself:

> You regularly accept chicken, rice bowls, mild Mexican flavors, and meals without cooked peppers. This recipe resembles three meals everyone usually approves.

The system should favor **precision over novelty**. Ten bizarre generated recipes nobody will eat are worse than one plausible new dinner.

### Preference inference

Over time, AI can identify possible patterns from actual voting data:

- ingredient preferences
- texture patterns
- cuisines
- sauce preferences
- spice tolerance
- preparation methods
- combinations that work or fail

These should be treated as inferred hypotheses, not permanent truths. Users should be able to correct them.

### Recipe normalization

AI can help turn messy pasted recipes, screenshots, or poorly structured webpages into clean recipe records.

### Recipe adaptation — later

Potentially suggest modifications that turn a near-match into something more acceptable to the household.

Example:

> The household tends to reject meals with cooked onions. This recipe can likely be made without them; use onion powder for flavor instead.

Any substitution or adaptation should be explicit rather than silently altering the source recipe.

## Suggested first version

The first useful version does not need AI.

### V1

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

If this replaces the spreadsheet successfully, it has already earned its existence.

### V1.5

- recipe URLs and pasted-recipe ingestion
- clean recipe display
- printing
- meal photos
- better filtering/categories
- "haven't had this lately" weighting
- automatic stale-meal suggestions

### V2

- preference modeling
- AI-assisted recipe discovery
- AI-assisted recipe normalization
- inferred household taste patterns
- suggested recipe adaptations

## Architecture thoughts

The product should probably be **web-first / local-network friendly rather than native-mobile-first** so everyone in the household can participate without installing an app.

A practical shape could be:

- desktop/web host or lightweight server
- responsive browser voting UI for household members
- persistent local database
- simple room/session codes similar in spirit to Pips
- optional hosted deployment later if remote participation becomes useful

Do not make accounts/authentication a prerequisite for the household use case unless deployment eventually demands it.

## Open design questions

These should be resolved through use rather than prematurely designed to death:

- How many meals should appear in a voting round?
- Should everyone vote on the entire pool or should the app progressively narrow candidates?
- Does "not tonight" count as rejection for the current round but neutral for long-term preference learning?
- Should a hard no automatically hide a meal from rounds involving that person?
- Should archived meals periodically be offered for reconsideration?
- Should the final chooser be random by default or manual?
- How much of the original D8/D20 ritual is worth preserving because it is fun?
- Should new recipe suggestions enter a probationary pool before becoming normal candidates?

## Success criterion

Dinner Decider succeeds if the household can answer **"what are we eating tonight?"** faster, with less negotiation, while gradually building a better list of meals everyone can actually agree on.
