# Demo video script

**Target: 2:40. Hard cap: 3:00** (hackathon rule — over 3:00 is disqualifying).
Upload to YouTube, **public** visibility (the rules require public, not unlisted).

Money shot lands at **0:38**. Most judges stop watching around 60–90 seconds, so
everything that wins is in the first minute.

---

## Before you record

Run this once — it resets state so the demo is repeatable:

```bash
cd "/Users/ritesh/Hackathon Projects/datahub-blast-radius"
docker ps                    # all 6 DataHub containers healthy
.venv/bin/blast-radius analyze --column orders.order_date --platform postgres
```

Setup checklist:

- [ ] Terminal font size **18pt or larger** — judges watch on laptops, some on phones
- [ ] Terminal window sized so the 47-line output fits without scrolling
- [ ] Browser zoom at 110–125% for the PR and DataHub tabs
- [ ] Close Slack, mail, notifications — nothing should pop up mid-take
- [ ] Tabs pre-opened in this order:
      1. `github.com/ritesh59697/demo-analytics/pull/1/files` (the diff)
      2. `github.com/ritesh59697/demo-analytics/pull/1` (the comment)
      3. DataHub Documentation tab (URL below)
- [ ] Hide bookmarks bar; use a clean browser profile if possible

DataHub Documentation tab (the writeback shot):

```
http://localhost:9002/dataset/urn%3Ali%3Adataset%3A%28urn%3Ali%3AdataPlatform%3Apostgres%2Cb2fd91.order_entry_db.order_entry.orders%2CPROD%29/Documentation
```

Record at 1080p minimum. QuickTime screen recording is fine.

---

## Shot list

### 0:00–0:12 — The problem, concretely

**Screen:** PR #1 "Files changed" tab. The `+2 −2` diff, nothing else.

> "This is a two-line pull request. It renames a column called `order_date`.
> It looks completely harmless."

*Let the diff sit on screen for a beat. Do not talk over it.*

---

### 0:12–0:24 — Why nobody catches it

**Screen:** Still the diff. Slowly scroll the two changed files.

> "A reviewer reads this diff. What they can't see is where that column goes —
> through S3, into Snowflake, through three dbt models, out to Looker,
> PowerBI and Tableau. No single tool shows all of that at once."

---

### 0:24–0:38 — Run it

**Screen:** Cut to terminal. Type the command live — it returns in under a second.

```bash
blast-radius analyze --column orders.order_date --platform postgres
```

> "DataHub already knows all of this. So we asked it."

---

### 0:38–1:05 — MONEY SHOT

**Screen:** The output, full frame. Hold on the top six lines. Do not scroll yet.

> "This change breaks one dashboard, two charts, and sixteen tables —
> twenty-one downstream entities, across seven platforms, six hops deep."

*Pause 2 seconds on `Order Entry Dashboard`.*

> "That's the Order Entry Dashboard, in Looker, six hops away from a
> two-line diff."

**Then** scroll slowly to the NOTIFY block.

> "And these are the people who own the things that break — pulled from
> DataHub ownership, ranked by how much of their surface is affected."

---

### 1:05–1:25 — On the pull request

**Screen:** Browser tab 2 — PR #1 conversation, showing the posted comment.

> "It posts that as a comment on the pull request, where the decision
> actually gets made. This is a real comment on a real PR."

*Scroll through the severity table and the "Who needs to know" list.*

---

### 1:25–1:45 — Severity means something

**Screen:** Terminal. Run the contrast case live:

```bash
blast-radius analyze --column customers.nls_language --platform postgres
```

> "A tool that flags everything gets ignored. Same warehouse, different
> column — medium, and it says why: no dashboards, no charts, no ML models.
> Severity is driven by what breaks, not how much."

*This beat exists because judges test exactly this.*

---

### 1:45–2:10 — Writing back to the graph

**Screen:** Browser tab 3 — DataHub Documentation tab on the `orders` dataset.

> "Reading lineage is the easy half. The verdict gets written back into
> DataHub — as a link on the dataset, and a HighBlastRadius tag."

*Point at the link label showing severity and scope.*

> "So the next person who touches this column — or the next agent —
> inherits the finding instead of rediscovering it."

---

### 2:10–2:30 — The migration plan

**Screen:** `examples/migration-orders.order_date.md` in an editor or on GitHub.

> "And because knowing what breaks isn't the same as knowing how to fix it,
> it generates the migration: ship a backwards-compatible alias first, then
> work through consumers nearest-first, each one attributed to its owner."

---

### 2:30–2:40 — Close

**Screen:** The repo README, top of page.

> "Blast Radius. Built on DataHub's column-level lineage, Apache 2.0,
> link in the description."

*End on the GitHub URL visible on screen.*

---

## Lines to avoid

- ❌ "Hi everyone, my name is…" — dead air, judges skip
- ❌ Explaining what DataHub is — the judges built it
- ❌ Walking through architecture or file structure
- ❌ "As you can see here…" — just show it
- ❌ Claiming column-precision into Looker (it is entity-level there — say
      "reaches" not "column-level in")

## Honesty guardrails

Everything shown must be real, because it is:

- The PR is a real PR. The comment was posted by the tool.
- The lineage is from the loaded `showcase-ecommerce` datapack, not mocked.
- Owner names are the datapack's synthetic fixtures — do not imply they are
  real people at a real company.
- Do not say "in production at…" or imply users.

## After recording

- [ ] Under 3:00
- [ ] Uploaded to YouTube, **Public** (rules require public)
- [ ] Title: `Blast Radius — DataHub Agent Hackathon`
- [ ] Description includes repo URL + demo PR URL
- [ ] Watch it once in an incognito window to confirm it plays
