# Teacher Gold reference vocabulary contract

This contract preserves the full human teacher-gold meaning when a verified
Sheet label is musically valid but the frozen authoritative `HarmonicIdentity`
vocabulary cannot encode it.

## Two separate truths

The benchmark layer now distinguishes:

1. **Reference truth** — the exact verified teacher label and expected state.
2. **Engine-executable truth** — the subset that can be represented completely by
   the current `HarmonicIdentity` contract.

A reference-only label is never converted into a different engine identity.
`engine_identity=None` means only "current engine vocabulary cannot encode this
teacher label". It does not mean the teacher label is invalid and it grants no
new resolver authority.

## Current known reference-only grammar

The bounded reference contract recognizes these already-observed teacher-label
families as musically valid but engine-unrepresentable:

- major sixth: `C6`
- minor sixth: `Dm6`
- suspended dominant seventh: `C7sus4`
- suspended dominant seventh with sus2: `C7sus2` (grammar reserved for the same
  vocabulary boundary)

Slash-bass spelling may be preserved as teacher text, but does not create a new
engine identity.

Unknown labels outside both the frozen engine vocabulary and this bounded
reference-only grammar still fail closed.

## Safety invariants

- `teacher_gold_adapter.py` remains unchanged and continues to reject any label
  not representable by `HarmonicIdentity`.
- No resolver, evidence precedence, confidence, ambiguity, abstention, public
  runtime, AI/model, or production authority is changed.
- Reference-only cases must not be silently included in an executable
  `TeacherGoldBenchmark`, because that would drop part of the human truth.
- `ABSTAIN` and `NO_MATCH` cases remain executable without candidate identities.
- The exact teacher label, inversion metadata, teacher reason, and public request
  are preserved in `TeacherGoldReferenceCase`.

## Coverage semantics

`TeacherGoldReferenceCoverage` reports:

- total reference cases,
- fully engine-executable cases,
- reference-only cases,
- exact case IDs that are reference-only,
- exact unsupported teacher labels.

This makes a result such as `90 executable / 10 reference-only` explicit instead
of treating the frozen 100-case calibration set as either wholly invalid or
silently truncating it.

## Frozen calibration validation

`validate_frozen_calibration_reference_v0_1()` validates the complete
`TG-0001` through `TG-0100` shape using the reference contract. This is separate
from the stricter executable adapter validation.

The reference contract is benchmark infrastructure only. It does not authorize
Stage 8, model training, model promotion, or a change to authoritative harmonic
resolution.
