# Aesop continuation: one-week measurement

## Selection

At the start of this continuation, branch `codex/foreman-v1` was clean at
`ade999054a8b79aaeaac96b62798a87399de032a`. The working v2 preview had a
one-day check only. The project brief requires configurable one-day and one-week
checks. This continuation's objective is an end-to-end one-week check with a
distinct held-out item, clock-controlled tests, and separate outcome reporting.

Using the mission weights (learning objective 30%, verified delivery 25%,
measurement 20%, architecture 15%, progress per dollar 10%), this objective was
favored over a probabilistic learner model and a broader experiment. The
one-week check fills a measurable workflow gap with bounded code and no runtime
AI or paid research call. These are qualitative priority judgments, not
empirical effect estimates. The one-week interval is a pilot default from the
brief, not an optimal interval established for these Python concepts.

## Design and scientific boundary

The v3 pack adds one seven-day trace item per concept, each with a family distinct
from the one-day item. All 22 items and five concepts are versioned v3. Existing
v1 and v2 packs remain unchanged and their learner histories remain pinned.
The new pack is draft, has candidate keys, and has no independent review
receipts. The v3 policy (`pilot-v2`) uses a saved lesson time, observed attempts,
and item-specific delay. A completed day-one check opens the week-one check even
when day-one was incorrect or assisted. Conditioning week-one eligibility on
day-one success would systematically omit weak outcomes.

Separate interval statuses distinguish an observed day-one answer from missing
week-one evidence. Assisted answers never count as independent success. Synthetic
clock progression verifies software behavior, not learning effectiveness. There
is no claim of mastery, human retention improvement, or causal benefit.

The choice to measure at a week is consistent with research using delayed tests
to distinguish immediate performance from later retention. For example,
[Karpicke and Roediger's retrieval experiment](https://doi.org/10.1126/science.1152408)
and [the retrieval versus study analysis of initially retrievable material](https://pubmed.ncbi.nlm.nih.gov/22304454/)
motivate delayed observation. Neither validates the effect of this app's new
items or policy; that requires reviewed content and learner data.

## Verification and limits

On this branch, `PYTHONPATH=src; py -m unittest discover -s tests -q`
passed 111 tests. `cd web; npm test` passed 16. The Python suite validates the
v3 pack, executes trusted authored snippets against candidate keys, advances a
test clock through practice and both checks, verifies independent versus
assisted evidence, tests v4-to-v5 SQLite migration, and pins historical v1/v2
learner records. `git diff --check` passed. Direct loopback HTTP returned the
v3 overview and distinct empty day-one and day-seven outcomes. Headless Edge
rendered the v3 evidence at 1440px and 390px without page errors or horizontal
overflow. The live isolated address is `http://127.0.0.1:8777/` with data at
`.local/foreman-v3.sqlite3`.

Independent non-author review and expansion to roughly 20 concepts remain open.
The fixed text-versus-diagram experiment was not changed. No paid provider or
model calls were launched, and no Claude or Cursor engineering package was
executed during this continuation; host token charges are unknown. Codex owned
implementation and verification, so the approximate equal-provider allocation
was not achieved. The hard $60 ceiling was not exposed to measurable paid calls.

The next three evidence-backed objectives are: (1) independent review and
correction of all v3 items and keys, (2) expand reviewed prerequisite coverage
toward 20 concepts, and (3) instrument exposure and missing-data records before
running the fixed comparison. None is claimed complete here.
