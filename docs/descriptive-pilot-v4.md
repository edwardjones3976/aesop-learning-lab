# Prospective descriptive pilot v4

V4 is for **new v7 learners only**. It has the same conditions, self-paced 10-minute study target, first-response rule, held-out families, and 7–14 day primary window as v3, with a new fixed seed (`20261020`) and the corrected v7 pack. Learners already on v1/v4, v2/v5, or v3/v6 remain pinned to their content, assignments, and exposure records, including after a restart or an interrupted session; mixed-version histories are still rejected.

Import `DESCRIPTIVE_V4`, `ExposureV4`, `assign_condition_v4`, and `analyze_v4` from `aesop_lab.experiment.descriptive_v4`. The local application routes v7 to protocol v4; every analyzer rejects another protocol's assignment and exposure records, and no earlier data is migrated. Draft candidate-key matches remain provisional, a single local learner cannot satisfy the 20-learner-per-arm minimum, and v4 reports `insufficient_evidence` with no teaching-method winner.
