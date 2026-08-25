# Stage 8 Sequence/Context Sampling Leakage Guard v0.1

Status: **metadata-only pre-assembly safety gate**.

## Scope

This guard runs after candidate mining/selection and before human-labeled TRAIN, VALIDATION or untouched SC-HOLDOUT cases are frozen. It does not select preferred candidates and does not authorize model selection, model training or production authority.

## Fail-closed checks

The guard blocks:

- duplicate candidate identities;
- duplicate exact current-frame fingerprints;
- the same source group appearing in more than one partition;
- the same score path appearing in more than one partition;
- the same source-score SHA-256 appearing in more than one partition;
- one score path changing source SHA-256;
- one source SHA-256 appearing under multiple score paths;
- sources outside the frozen 1,200-case source plan.

Multiple distinct ambiguity frames from the same score are allowed **only inside the same partition**, because the sampling policy already caps their final contribution and group isolation prevents split leakage.

## Complete freeze mode

With `require_complete_allocation=True`, the guard additionally requires the exact frozen allocations:

- OpenScore String Quartets: 400 TRAIN / 100 VALIDATION / 100 HOLDOUT;
- OpenScore Lieder: 200 TRAIN / 50 VALIDATION / 50 HOLDOUT;
- owned synthetic guitar/context: 200 TRAIN / 50 VALIDATION / 50 HOLDOUT.

Total: 800 TRAIN / 200 VALIDATION / 200 HOLDOUT = 1,200 cases.

Candidate-set types are intentionally allowed to appear across partitions; the guard isolates source instances and exact frames rather than preventing the same ambiguity class from being evaluated out of sample.
