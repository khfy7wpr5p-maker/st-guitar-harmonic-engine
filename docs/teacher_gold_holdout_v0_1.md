# Teacher Gold HOLDOUT v0.1

The holdout is a separate human-annotation partition reserved for final evaluation.
It is not calibration material and must not be used to tune resolver rules, model
training, thresholds, prompts, or candidate-vocabulary decisions.

## Namespace

- Calibration v0.1: `TG-0001` through `TG-0100`
- Holdout v0.1: `TG-0101` through `TG-0200`
- The two namespaces must remain disjoint.

## Sheet contract

The holdout uses the same eight-column human annotation schema:

1. `example_id`
2. `input_notes`
3. `expected_state`
4. `primary_candidate`
5. `acceptable_alternatives`
6. `inversion`
7. `teacher_reason`
8. `annotation_status`

The initial holdout template contains only the 100 reserved IDs and
`annotation_status=DRAFT`. No calibration labels are copied into it.

## Leakage boundary

Before freeze:

- DRAFT rows may be empty or partially annotated.
- DRAFT rows are never benchmark truth.
- Engine/model predictions must not be written into teacher-gold fields before human
  adjudication is complete.
- Holdout examples must not be used to change resolver precedence, vocabulary,
  confidence, abstention, model parameters, prompts, or calibration decisions.

At freeze:

- all 100 rows must be `VERIFIED`;
- each VERIFIED row must pass the existing reference-truth contract;
- known reference-only labels remain reference-only and are never coerced into an
  authoritative `HarmonicIdentity`;
- any missing/invalid row causes fail-closed rejection.

## Code boundary

`teacher_gold_holdout.py` provides two distinct gates:

- `validate_holdout_template_v0_1()` permits ongoing DRAFT annotation while enforcing
  the exact schema and `TG-0101..TG-0200` namespace.
- `build_frozen_holdout_reference_v0_1()` refuses to build a holdout until 100/100
  rows are VERIFIED and reference-valid.

This module does not change runtime harmony decisions and does not authorize Stage 8,
AI/model promotion, or a musical-accuracy claim. `BENCHMARK_READY` should not be
claimed until a frozen holdout has actually been built and evaluated separately from
calibration.
