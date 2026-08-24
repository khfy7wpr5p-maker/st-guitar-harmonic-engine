# Stage 8-0 deterministic baseline seal v0.1

Stage 8 begins from a frozen deterministic reference point. This contract seals one
Teacher-Gold evaluation without changing harmonic authority or authorizing model
training.

## Inputs

The seal is built from:

- one `TeacherGoldEvaluationReport`;
- the exact 40-character engine commit SHA;
- SHA-256 of the frozen calibration source;
- SHA-256 of the frozen untouched holdout source;
- Teacher-Gold vocabulary v0.3.

Private Teacher-Gold rows are **not** stored in the repository. Source digests may
be recorded in a private evaluation artifact together with the seal.

## Integrity/readiness gate

`READY` requires all of the following:

1. exactly 200 reference cases;
2. exactly 200 engine-executable cases;
3. zero reference-only cases;
4. exactly 100 calibration and 100 holdout cases;
5. zero validation/runtime errors;
6. deterministic-stable evaluation output.

These are integrity and reproducibility requirements only.

## Accuracy is not a hidden Stage 8 gate

The seal records:

- musical accuracy;
- state accuracy;
- identity accuracy;
- calibration split metrics;
- holdout split metrics.

No implicit accuracy threshold is used to decide `READY`. Any future performance
threshold must be a separate explicit contract and review. This prevents Stage 8
from silently changing the deterministic baseline policy to favor a model.

## Authority boundary

The seal does **not**:

- alter resolver evidence precedence;
- change ambiguity or abstention rules;
- tune from the holdout set;
- expose Teacher-Gold rows publicly;
- permit AI/model output to mutate authoritative harmonic state;
- authorize Stage 8 model promotion.

The deterministic engine remains authoritative.

## Private execution flow

```text
Frozen Calibration CSV (private) ---- SHA256 ----\
                                                \
                                                 +--> Teacher-Gold v0.3 assembly
                                                /             |
Frozen HOLDOUT CSV (private) -------- SHA256 --/              v
                                                    deterministic evaluation x2
                                                              |
                                                              v
                                                    Stage 8-0 baseline seal
                                                              |
                                                   READY or BLOCKED + metrics
```

The holdout source is evaluated for the baseline seal but is not used for tuning.
If a later model or policy is changed, the holdout remains final-validation data;
repeated optimization against it is prohibited.

## Self-hash

The canonical serialized seal payload is SHA-256 hashed. The resulting
`seal_sha256` makes accidental mutation of the metrics, source fingerprints, or
engine commit detectable.

## Stage transition

A `READY` Stage 8-0 seal permits work to continue to Stage 8-A data governance and
Stage 8-B feature-contract infrastructure. It does not itself authorize training,
production use, or model decision authority.
