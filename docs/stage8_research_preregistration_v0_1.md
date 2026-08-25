# Stage 8 Research Preregistration v0.1

This contract freezes the metadata of a future shadow-research design before any model-training plan may be proposed. It does not select the research target itself and never grants training or production authority.

## Required bindings

- canonical `target_id` and `objective_id`;
- one predefined primary metric;
- SHA-256 of the governed dataset manifest;
- exact deterministic engine commit SHA used as baseline;
- fixed train/validation case counts;
- zero Teacher-Gold and HOLDOUT overlap;
- HOLDOUT must not be used for model selection;
- research target must not be derived from HOLDOUT labels;
- Stage 8-A data governance must already pass;
- the target must be separately authorized;
- preregistration must be frozen before any training begins.

The contract emits a deterministic SHA-256 fingerprint over the full preregistration metadata. Changing the metric, corpus counts, target, dataset manifest or engine baseline changes the digest and therefore creates a different research plan.

`RESEARCH_DESIGN_PREREGISTERED` means only that the metadata is frozen and leakage/governance gates passed. `model_training_authorized` and `production_authority_granted` remain permanently false.

## Primary metrics available in v0.1

- false-resolution rate;
- candidate top-1 accuracy;
- ambiguity recall;
- abstention F1;
- OOD rejection rate.

## Out of scope

No research objective is chosen here. No raw examples, feature schema, model architecture, optimizer, training command, threshold, Teacher-Gold tuning, HOLDOUT tuning, inference runtime or production promotion is added by this contract.
