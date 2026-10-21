# Per-learner teaching-method ranking: design and recovery prototype

Owner goal, 2026-10-21: “The program should give feedback on distinct learning styles, in order from most effective to least, per user. It may change based on more results but it should have an answer within a reasonable time.”

Interpretation: estimate which **teaching methods** are associated with this learner's strongest delayed unassisted results on comparable material. Do not diagnose a learning style, infer a stable trait, or treat a preference as evidence of effectiveness. This is a new personal product layer. The descriptive group protocol, its assignments, classifier, reports, gates, UI and packs remain unchanged by this task.

## Methods and authored content

Use a versioned method registry with arbitrary N IDs, display names, prerequisite rules, lesson recipes and content versions. Persist the recipe actually delivered. Every comparison uses matched objectives, comparable study budgets (the current suggested target is ten minutes), common feedback and common held-out assessment specifications. A method is a complete instructional recipe, not an unlogged mixture of ingredients.

| Method | Per-concept content and implementation work | Evidence and boundary |
|---|---|---|
| `text` (existing) | Versioned explanation, worked code, reasoning, practice, hints and fresh delayed families. Preserve the existing baseline, which already includes examples and retrieval practice. | Baseline comparison; no claim that reading alone is optimal. |
| `diagram` (existing) | Same text and tasks plus an accessible labeled binding, call-stack or control-flow diagram, with equivalent text alternative. Author and independently check each label and arrow. | Candidate representation for this material; its incremental value is the question being measured. |
| `worked_first` (candidate) | Reorder instruction to begin with a fully solved, annotated trace, then explain the rule, then a faded completion task. Need a distinct example, intermediate states, fading steps and a separate practice family. | Worked-example experiments support novice problem learning; effects depend on prior knowledge and task. Existing text already contains worked examples, so this tests order/fading, not examples versus none. See [Sweller and Cooper, 1985](https://doi.org/10.1207/s1532690xci0201_3). |
| `retrieval_first` (candidate) | One short prediction question before the explanation, explicit corrective feedback, then the common lesson and practice. Need a prequestion family and misconception feedback that never disclose held-out families. | [Richland, Kornell and Kao, 2009](https://pubmed.ncbi.nlm.nih.gov/19751074/) found benefits of prequestions even after failed retrieval in prose learning. This does not establish the effect for Python or every learner. |
| `self_explanation` (candidate) | Insert two or three “why does this binding/return change?” prompts into examples, with model explanations and a human/self-review rubric. Do not auto-grade open explanations as objectively correct. | [Chi et al., 1989](https://asu.elsevierpure.com/en/publications/self-explanations-how-students-study-and-use-examples-in-learning/) observed productive explanations while students studied worked mechanics problems. This supports the mechanism, not a causal individual-style claim. |
| `interleaved` (candidate) | Matched mixed sets that alternate related confusable operations (e.g. local rebinding, parameter defaults, recursive return), with prerequisite tags and discrimination feedback. Need several new practice families, balanced blocked counterparts, and a versioned sequence. | [Dunlosky et al., 2013](https://pubmed.ncbi.nlm.nih.gov/26173288/) rated interleaving and self-explanation promising but less broadly established than practice testing. Interleaving is a sequence-level intervention: assign a whole practice block, not one isolated question. |

These sources motivate candidates; they do not validate this app's recipes or individualized matching. Start with two methods and add one candidate only when matched content exists. The recovery study below tests four methods; its sample sizes must not be reused as validated thresholds for six or arbitrary N. The estimator and assignment algorithm accept N, and the study can be rerun with a different scenario tuple.

## Unit of comparison and sufficient observations

`experiment/descriptive_v2.py:_assign_condition` assigns one method per concept per learner. Five concepts yield only two or three observations per method; neither a clever estimator nor pooled learners can create missing personal evidence. The separate scope comparison has four dependent micro-units and is also too small.

Recommended unit: a **fresh instructional micro-unit**, prospectively assigned to one method, with one previously unseen, unassisted day-seven application/trace family. Expand to related but meaningfully distinct sub-concepts and concepts; block prospective allocation by topic, prerequisite level and estimated difficulty. Retain concept, block, exposure, family, delay, method/recipe and key versions. Naming or numeric substitutions of a previously seen algorithm are not new independent units. Never teach the same material twice under different methods and count the later result as a clean comparison.

| Expansion option | Content cost | Treatment in the first estimator |
|---|---|---|
| More concepts/sub-concepts (recommended) | Each unit needs N matched lesson variants, practice/hints and at least one fresh week-check family with independently checked key; existing day-one practice/check scheduling also needs distinct content. At K observations this costs K fresh assessed units, not K answer attempts. | One day-seven result per unit, weight 1. Preserve topic balance and monitor dependence. |
| Several method-assigned units within one concept | N variants for each genuinely different micro-unit, matched objectives and difficulty, separate example/practice/held-out families, and carryover audit. | Do not switch methods between answers after shared instruction. Assign before exposure. Correlated units require cluster sensitivity checks; same-exposure checks have total weight at most 1. |
| Multiple delayed items after one exposure | Additional structurally distinct held-out families and grading review, no extra lesson variants. | Split the unit's total weight (e.g. two items at 0.5 each). This improves measurement of that unit, not the number of independent exposures. |
| Add day-one and practice scores | Separate day-one families and untouched day-seven families; assisted practice still excluded. Reusing practice reduces authoring but contaminates delayed assessment. | Keep separate descriptive panels initially. A future sensitivity model could allocate 0.75 week + 0.20 day-one + 0.05 unassisted practice per unit, but it changes the estimand and is **not** evidence for seven-day recall. No “clear” from this unvalidated mixture. |

For four methods the recommended first answer needs eight effective week checks, ideally two per method; reliable identification in the ideal recovery study needs substantially more. The current five-concept pack cannot even reach eight fresh concept-level outcomes. Expanding to the brief's approximately twenty concepts can enable an early answer, but does not ensure an accurate winner. The current finite packs cannot supply the full simulation horizon. Content expansion is a prerequisite to deployment, not implemented here.

## Estimator contract

`src/aesop_lab/ranking/method_ranking.py:rank_methods` is a pure function with no storage, clock, protocol, UI or global random-state effects. Input is a mapping of every candidate method ID to `(matched_key: bool, weight: float)` observations, including empty lists for methods not yet observed. Valid weights are finite in [0,1]; zero is ignored. The caller must filter and deduplicate first: weights do not prove independence or eligibility.

For method m, use a weak symmetric Beta(1,1) prior and fractional Bernoulli likelihood:

`alpha_m = 1 + sum(weight * match)`; `beta_m = 1 + sum(weight * (1-match))`.

The posterior mean is `alpha/(alpha+beta)`. Independently sample all beta posteriors 2,048 times with an injected local seed; P(best) is the fraction won. Maximum Monte Carlo standard error is about 1.1 percentage points. Order by posterior mean, with stable method-ID ties. Return all rows with mean, P(best), effective weight, alpha and beta, plus one **leader confidence** label and a display flag. Confidence never asserts the whole order is correct. A method can have the highest mean without the highest P(best); its own P(best) controls its leader label. Close or exact ties remain explicitly tentative. P(best) is conditional model uncertainty, not a frequency guarantee about real learners.

This is a power-likelihood prototype for weights; fractional counts are not literal binomial sample sizes. Independent beta arms ignore item difficulty, topic effects, correlated answers and time trends. A production successor should model those effects, validate held-out predictions, and compare cluster-adjusted rankings before relying on strong labels.

Optional future partial pooling: learn population priors by method/topic from other consented learners, with a learner-specific effect and modest capped prior strength. Fit without using the target learner's future results; display how much evidence is personal versus borrowed. Do not count observations from other people as this person's checks or remove the personal minimum. No pooling is implemented or needed in this prototype.

### Classifier boundary

Build a future adapter over the existing classifier outputs without rewriting historical classification. Only the first scored unassisted response to a fresh family at days 7–14 after completed compatible exposure contributes to this seven-day model. Reviewed `eligible` outcomes and draft `provisional` key matches must be kept identifiable; draft data can support a personal **draft-key** ranking but never become eligible group outcomes. Do not silently mix key versions or reviewed and draft targets.

Missing, invalid, incomparable exposure, ungraded, assisted, contaminated, previously seen and early outcomes do not become failures. Late independent results retain actual elapsed delay and a descriptive count but do not enter this model. Day-one checks are early relative to this target. A later correct attempt cannot replace the decisive first response. Respect each source protocol's outside-study rule: later descriptive versions exclude reported study; scope-v2 additionally excludes unknown declarations, standard-path exposure and questions open over thirty minutes. Unknown status is not proof of no outside study. The estimator deliberately receives none of these metadata; callers remain responsible for that provenance and for showing exclusion counts.

## Answer rule and reasonable time

1. Before eight effective delayed checks (or 2N when larger), show progress and what check is next. The function returns the full ordering even then, with `show_ranking=False`.
2. At `sum(weights) >= max(8, 2N)`, **always show all methods in order** and update after every accepted result. Do not return a silent “insufficient evidence” in this personal view. No per-arm gate can suppress the answer after this total minimum: unobserved methods stay visible with their prior mean, zero count and “not yet tested.” Freeze the available method roster per evidence version; adding candidates must not hide an already displayed answer.
3. **Tentative** is the default, including sparse arms, ties and weak separation. Show the count per method; explain when untested methods are ordered mainly by the prior. Equal means are displayed as tied with a deterministic row order.
4. **Likely** requires at least two candidate methods, at least five effective checks for **every** method and the mean-ranked leader's conservative Monte Carlo probability bound >= 0.80.
5. **Clear** requires at least twenty effective checks for **every** method and that bound >= 0.99. The bound is `p - 2*sqrt(p*(1-p)/draws) - 1/draws`; it guards sampling noise, not model error. Also require valid independent unit provenance and stable content/recipe definitions in a future adapter. Correlation, unvalidated outcome mixtures or unresolved key faults prohibit a product “clear” claim regardless of the raw function label.
6. Labels may downgrade and the order may reverse. Keep displaying the ranking; log the evidence version and update timestamp. A “clear” leader means clearer separation **on these draft-key checks under the model**, not verified educational superiority or a permanent trait.

The early eight-check threshold is an availability promise, not an 80%-accurate identification promise. The all-arm floors stop a lucky beginning from receiving a strong label while alternatives are barely tested. The 0.99 threshold deliberately makes “clear” uncommon. Do not lower it simply to get an answer faster: the tentative answer is already available.

## Adaptive assignment, separate from the descriptive protocol

For new personal-layer material only, assign two units per method in balanced randomized warm-up. Thereafter choose uniformly among N methods on 20% of assignments and use Thompson sampling from the observed beta posteriors on the remaining 80%. Every method thus has an exploration floor of 0.20/N. The simulation's `choose_method` implements this policy for arbitrary N. Warm-up uses assignment counts (including pending units), avoiding seven-day-delay over-allocation to one unobserved arm. Subsequent sampling uses only received outcomes, never synthetic future answers.

Persist method, probability of assignment, seed/draw, eligible choices, block/topic, recipe version and policy version **before exposure**; reuse after restart. Honor prerequisites and learner overrides, record overrides, and preserve the fresh assessment families. Due checks retain priority. Do not concentrate exploration on easier topics or allocate after observing an answer. Uniform exploration is a floor, not a guarantee of twenty observations per arm by a particular date.

Existing concept assignments remain fixed under their enrolled descriptive protocol. Never replace `_assign_condition` with a bandit, change historical assignments, or feed adaptive product units into the unchanged group comparison. Read-only historical evidence can initialize a separately labeled personal view if provenance and target match. Future adaptive units need a new namespace/policy and are excluded from the fixed group analysis. Interleaving requires block assignment and block-level uncertainty rather than pretending each interleaved question is a separate intervention.

## Recovery study

Run from the repository root:

```powershell
$env:PYTHONPATH='src'
python scripts/method_ranking_recovery.py
python -m unittest discover -s tests -q
```

The script uses 500 independent synthetic learners per gap, known four-arm recall probabilities, Beta(1,1) priors, the same estimator and label thresholds, and the adaptive policy above. Rotate the best method's ID across learners so tie-breaking cannot favor it. Master seed is 20261021, with separate scenario/learner seeds and a separate estimator RNG. Outcomes are independent Bernoulli draws at the known per-method probability. A seven-day pending queue prevents assignment from observing future feedback.

The app is self-paced: it has ten-minute suggested exposures, one-day/week check gates and a 7–14 day week window, **not a fixed units-per-day schedule**. The main simulation assumes one new distinct unit each day, routine practice/day-one requirements completed, one fresh scored week check per unit exactly seven days later, all visits attended, and enough content. Day zero is first exposure; check K arrives on day K+6. This is a scenario compatible with current delay gates, not an observed human rate or a guarantee. `--units-per-day` changes throughput and the pending-feedback assignment process; missing visits, contamination and practice prerequisites can only delay accumulation relative to this ideal. With fewer than eight usable units the first-answer target is unreachable regardless of days waited.

At checkpoints 8,16,32,64,128,256,512,1024, measure how often the posterior-mean leader is the known true best. Report the first checkpoint with >=80% recovery **and all later tested checkpoints >=80%**, rather than a lucky early crossing. This is ensemble identification, not a claim that any individual has an 80%-correct leader at that count. Report Wilson intervals across independent learners. Error among “clear” labels is also recorded at checkpoints, with a separate first-clear rate and learner-level ever-wrong count; repeated checkpoint decisions are dependent and must not be pooled into a binomial confidence interval. This study does not evaluate daily repeated-look error between checkpoints.

Completed run: 500 learners per gap, 2,048 posterior draws per report, master seed 20261021. All later tested checkpoints remained above 80% after each reported crossing.

| Gap | Known recall probabilities | First sustained >=80% checkpoint | Simulated day | True best ranked first (95% Wilson) | First-clear errors / learners first labeled clear |
|---|---|---:|---:|---|---|
| Large | 0.80, 0.60, 0.45, 0.30 | 32 | 38 | 80.6% [76.9, 83.8] | 0/483; 0.0% [0.0, 0.8] |
| Medium | 0.80, 0.65, 0.55, 0.45 | 64 | 70 | 84.2% [80.7, 87.1] | 0/416; 0.0% [0.0, 0.9] |
| Small | 0.65, 0.60, 0.55, 0.50 | 1024 | 1030 | 90.4% [87.5, 92.7] | 0/10; 0.0% [0.0, 27.8] |

Across the sampled checkpoints, no learner ever received a wrong clear label (0/500 in each scenario). This is not evidence of zero risk: especially for the small gap, only ten learners received any clear label. Its first-clear error interval extends to 27.8%. The first crossing is checkpoint resolution, not an exact stopping time; for example the small-gap 80% crossing lies after 512 and at or before 1024 checks on this grid. The large-gap interval at 32 includes values below 80%; its first checkpoint with the lower interval bound above 80% is 64.

Full checkpoint results (clear-label counts are out of 500 learners at that checkpoint; n/a means no clear labels):

| Gap | Checks | Day | True best ranked first (95% Wilson) | Clear labels | Wrong / clear |
|---|---:|---:|---|---:|---|
| large | 8 | 14 | 57.0% [52.6, 61.3] | 0 | n/a |
| large | 16 | 22 | 66.6% [62.4, 70.6] | 0 | n/a |
| large | 32 | 38 | 80.6% [76.9, 83.8] | 0 | n/a |
| large | 64 | 70 | 93.2% [90.6, 95.1] | 0 | n/a |
| large | 128 | 134 | 98.0% [96.4, 98.9] | 0 | n/a |
| large | 256 | 262 | 100.0% [99.2, 100.0] | 28 | 0.0% [0.0, 12.1] |
| large | 512 | 518 | 100.0% [99.2, 100.0] | 367 | 0.0% [0.0, 1.0] |
| large | 1024 | 1030 | 100.0% [99.2, 100.0] | 475 | 0.0% [0.0, 0.8] |
| medium | 8 | 14 | 45.0% [40.7, 49.4] | 0 | n/a |
| medium | 16 | 22 | 58.8% [54.4, 63.0] | 0 | n/a |
| medium | 32 | 38 | 73.4% [69.4, 77.1] | 0 | n/a |
| medium | 64 | 70 | 84.2% [80.7, 87.1] | 0 | n/a |
| medium | 128 | 134 | 94.6% [92.3, 96.3] | 0 | n/a |
| medium | 256 | 262 | 99.6% [98.6, 99.9] | 25 | 0.0% [0.0, 13.3] |
| medium | 512 | 518 | 99.8% [98.9, 100.0] | 210 | 0.0% [0.0, 1.8] |
| medium | 1024 | 1030 | 100.0% [99.2, 100.0] | 404 | 0.0% [0.0, 0.9] |
| small | 8 | 14 | 36.0% [31.9, 40.3] | 0 | n/a |
| small | 16 | 22 | 34.4% [30.4, 38.7] | 0 | n/a |
| small | 32 | 38 | 36.0% [31.9, 40.3] | 0 | n/a |
| small | 64 | 70 | 48.8% [44.4, 53.2] | 0 | n/a |
| small | 128 | 134 | 55.0% [50.6, 59.3] | 0 | n/a |
| small | 256 | 262 | 68.2% [64.0, 72.1] | 0 | n/a |
| small | 512 | 518 | 78.2% [74.4, 81.6] | 0 | n/a |
| small | 1024 | 1030 | 90.4% [87.5, 92.7] | 10 | 0.0% [0.0, 27.8] |

These results justify an **availability** threshold of eight checks with a tentative label: at day 14, true-best identification was only 57.0%, 45.0% and 36.0% for large, medium and small gaps. Five checks per method plus a conservative 0.80 posterior bound is a model-based likely threshold, not a promise of reliable identification by day 14. Twenty per method plus a conservative 0.99 bound made clear labels rare and produced no observed checkpoint errors, but requires human and repeated-look validation before any real-world error guarantee.

Do not promise a reliable winner within two weeks, or disguise small differences with a clear label. Even ideal medium-gap identification needed 64 genuinely new assessed units (70 days at the assumed pace). Near-equal methods needed over two years in this simulation and may never separate within a sustainable course. Keep showing their ordered estimates with a tentative/close explanation instead. The four-method first-answer target can be met around two weeks only after expanding content; current five-concept content cannot meet it. Neither the current pack nor a twenty-concept pack supports the study's long horizons without substantial additional authored and independently reviewed units.


## Learner wording

Tentative: “So far, worked examples are first in your ranking (tentative). You have 8 later checks. The order may change as you answer more.”

Likely: “So far, worked examples help you remember best (likely). Your answers matched the draft key more often on later questions with this method.”

Clear, only within the boundary above: “Worked examples currently lead on your later draft-key checks (clear under this model). This can change with new topics and results.”

Evidence detail: “Estimated chance of matching the draft key on a comparable later question: 72%. Estimated chance this method leads among the methods tested: 84%. Based on 18 effective checks. Draft keys and differences between questions can affect the order.” These are illustrative numbers, not study results. Show both raw and effective counts if weighted. Mark lower-ranked close methods as close; the leader's label does not certify every pairwise ordering. Explain untested methods and excluded outcomes in plain language. Use “matched the draft key,” never “mastery” or “you are a visual learner.”

## Scope, risks and review before deployment

This task supplies a design, isolated estimator, unit tests and synthetic recovery evidence. It does not change protocol modules, classification, scheduling, UI, packs, exports, databases, permissions or enrollment. It does not provide a live adapter or deploy a bandit. Independent review and repository gates remain required; this work must not approve or merge itself.

Open risks: insufficient fresh content, fatigue/dropout during long studies, recipe overlap, unequal attention/time, topic difficulty confounding, practice selection effects, carryover between units, correlated failures, outside study, adaptive selection and missed-check bias, drift with experience, draft key faults and deterministic scoring limitations. The scope of a method ranking is the tested tasks and delay, not broad understanding, transfer or lifelong learner identity. Longer exposure to a method can itself change its value. A fixed-probability simulation is optimistic and cannot establish real-world recovery, calibrated confidence, accessibility or educational efficacy.

Before stronger product claims, obtain qualified independent content/key review, audit family independence and difficulty, run clustered/missingness/drift sensitivity studies and a prospective human feasibility study. Collect real sustainable pacing and acceptance rates. Compare recommendations with a competent fixed routine; a correct arm ranking alone does not prove the adaptive system improves outcomes. No cloud aggregation, psychological profiling or automatic grading of open explanations is in scope.

## Prototype validation

On Python 3.12, `PYTHONPATH=src python -m unittest discover -s tests -q` passed all 294 tests, including nine new tests covering the analytic two-arm P(best), N methods, fractional weights, invalid inputs, deterministic replay, no mutation, confidence floors, rank reversals, balanced warm-up and the seven-day feedback queue. `python -m compileall -q src tests scripts/method_ranking_recovery.py` passed. Existing web unit tests (17) and web contract tests (51) also passed. Browser tests were not run for this isolated estimator/design change. No coverage tooling or coverage gate is configured in this repository, so line/branch/function coverage is unavailable; no coverage percentage is claimed. The completed recovery run is recorded above. Independent review remains pending.
