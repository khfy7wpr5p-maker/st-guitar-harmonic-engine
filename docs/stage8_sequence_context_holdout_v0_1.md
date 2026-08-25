# Stage 8 Sequence/Context Untouched Holdout v0.1

Status: CONTRACT ONLY. No holdout rows are committed by this change.

## Purpose

The SC training corpus has TRAIN and VALIDATION partitions. Final model generalization must be measured on a separate untouched 200-case holdout that cannot participate in feature selection, model selection, threshold tuning, hyperparameter tuning, or target derivation.

## Namespace and count

The holdout namespace is exactly:

- `SCH-00001` through `SCH-00200`
- exactly 200 cases are required before freeze readiness

The v0.1 source allocation is inherited from the frozen sample plan:

- 100 OpenScore String Quartets cases
- 50 OpenScore Lieder cases
- 50 project-owned synthetic guitar/context cases

## Isolation rules

1. Every case must have a source-item SHA-256 and deterministic candidate-set SHA-256.
2. Every case must remain disjoint from Teacher-Gold, Teacher-Gold HOLDOUT, and the SC training corpus.
3. No source group present in TRAIN or VALIDATION may appear in SC-HOLDOUT.
4. The entire 200-case holdout must be human VERIFIED before it can be frozen.
5. Human review may select exactly one deterministic candidate or explicit `no_preference`.
6. Candidate generation during review is forbidden; the candidate set is immutable.
7. Source rights governance must pass for every retained case.
8. The holdout feature-contract version and deterministic engine SHA are recorded with each case.
9. Raw source score/audio payloads are not committed to this public repository.

## Evaluation boundary

`HOLDOUT_FREEZE_READY` means only that the 200-case metadata/annotation corpus can be frozen as an untouched final test set. It does not authorize:

- model selection
- model training
- feature changes
- threshold changes
- production authority

The holdout must be frozen before model selection begins. It may be opened only after the candidate ranker, feature schema, model artifact, and selection policy are frozen. If the holdout result is poor, a future research version must be preregistered rather than repeatedly tuning on the same SCH cases.
