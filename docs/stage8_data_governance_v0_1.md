# Stage 8-A Data Governance v0.1

This contract governs aggregate research-data provenance and rights metadata only. It does not authorize model training, promote a model, change deterministic resolver authority, or copy private Teacher-Gold/HOLDOUT rows into the repository.

## Safety invariants

- Teacher-Gold and HOLDOUT remain evaluation-only and disjoint from any training/validation candidate source.
- Any Teacher-Gold/HOLDOUT overlap or target derivation from HOLDOUT labels fails closed.
- Sources containing personal data fail closed at this stage.
- Training/validation candidates must use a frozen snapshot with SHA-256 provenance and content fingerprints.
- Training/validation candidates require confirmed training rights and commercial-use permission.
- `NONCOMMERCIAL` and `UNKNOWN` license classes cannot be training/validation candidates.
- Noncommercial sources may remain `REFERENCE_ONLY` when otherwise safe; reference-only data is never counted as a training candidate.
- Duplicate source IDs or duplicate content snapshots fail closed.
- At least one valid `TRAIN_CANDIDATE` is required before dataset design can be called eligible.

`DATASET_DESIGN_ELIGIBLE` means only that the aggregate manifest is safe enough to design a future research dataset. It is **not** model-training authorization. `model_training_authorized` and `production_authority_granted` are permanently false in this contract.

## Commercial-safety implication

A source with noncommercial terms (for example a CC BY-NC-SA family source) must not be used as a training or validation candidate for a future commercial model unless a separate explicit right is obtained. It may be retained as reference-only metadata when no other gate is violated.

## Scope exclusions

No raw corpus ingestion, dataset construction, train/validation split generation, feature extraction, model code, dependency addition, threshold selection, HOLDOUT tuning, network access, or production runtime change is part of v0.1.
