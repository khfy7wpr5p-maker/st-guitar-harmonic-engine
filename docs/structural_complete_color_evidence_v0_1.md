# Structural Complete Color Evidence v0.1

## Purpose

Teacher-Gold calibration exposed a conservative decision-policy gap: complete natural-extension and altered-dominant structures could already be identified by the deterministic engine, but they carried only `COLOR_TONE` evidence and were therefore withheld as weak evidence.

This maintenance change adds `STRUCTURAL` evidence only when an existing Stage 2 producer has already proven a complete supported base chord plus exactly one permitted color tone.

## In scope

- complete-base natural 9th/11th/13th candidates produced by `generate_extension_candidates`;
- complete dominant-seventh plus one canonical b9/#9/#11/b13 candidate produced by `generate_altered_tension_candidates`.

These candidates carry:

`STRUCTURAL + COLOR_TONE`

The existing Stage 4 strength contract therefore classifies them as `BOUNDED`.

## Explicitly unchanged

- exact evidence and precedence;
- suspended-chord candidates remain `COLOR_TONE` only;
- incomplete-chord candidates remain `INCOMPLETE_CHORD` only;
- no generic upgrade of `COLOR_TONE` evidence;
- no AI/model evidence or authority;
- no vocabulary expansion;
- no holdout-derived tuning;
- no Stage 8 authorization.

## Safety rationale

The structural claim is not inferred from the color tone alone. It is granted only because the existing producers already require the complete supported base structure and exactly one bounded, enumerated extension/alteration. Ambiguous candidate sets remain ambiguous under the resolver; only uniquely supported structural candidates can become resolved through the existing precedence and abstention contracts.
