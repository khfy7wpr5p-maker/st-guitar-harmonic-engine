# Teacher Gold holdout candidate QC v0.1

This QC layer answers one bounded question: is the proposed `TG-0101..TG-0200`
DRAFT set structurally and musically encoded well enough to hand to the human
teacher for adjudication?

It does **not** convert DRAFT into VERIFIED and does not freeze or evaluate the
holdout.

## Review-ready checks

- exact 100-row holdout namespace and v0.1 Sheet schema,
- every proposed row can pass the existing reference-truth validator when its
  status is privately substituted with `VERIFIED` for validation only,
- DRAFT source status is never mutated,
- expected-state distribution is reported but not optimized against runtime,
- reference-only sixth/suspended-seventh cases are reported explicitly,
- calibration and holdout are compared by sounding pitch-class set so a case
  cannot be hidden as "new" merely by changing octave or enharmonic spelling.

## Leakage boundary

The overlap check consumes only teacher-gold source rows. It does not read model
predictions, runtime outputs, resolver scores, or benchmark results. A holdout
candidate that reuses a calibration pitch-class set is rejected from
`review-ready` status until the DRAFT proposal is changed.

The QC layer has no authority over resolver precedence, ambiguity, abstention,
confidence, model training, promotion, or production behavior.

## Human gate

`is_review_ready=True` means only that the 100 DRAFT proposals are ready for
human musical review. The holdout remains unusable for final evaluation until
all 100 rows are independently adjudicated and marked `VERIFIED`, after which
the separate holdout freeze contract must pass.
