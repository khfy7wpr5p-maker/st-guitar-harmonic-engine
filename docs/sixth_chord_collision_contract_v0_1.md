# Sixth-chord collision contract v0.1

## Purpose

This contract records why `6` and `m6` remain reference-only after Teacher-Gold vocabulary v0.2. It is a diagnostic and safety boundary, not a sixth-chord runtime implementation.

## Exact pitch-set collisions

For any root `R`:

- `R6` has pitch classes `{R, R+4, R+7, R+9}` and is identical to the relative minor-seventh pitch set rooted at `R+9`;
- `Rm6` has pitch classes `{R, R+3, R+7, R+9}` and is identical to the relative half-diminished-seventh pitch set rooted at `R+9`.

Examples:

- `C6` = pitch set of `Am7`;
- `Cm6` = pitch set of `Am7b5`.

Therefore pitch content alone cannot establish which harmonic root/family is intended.

## Fail-closed policy

The current engine must preserve ambiguity for this collision unless an explicitly permitted higher-context rule exists.

At contract v0.1:

- `TONAL_CONTEXT` is the only evidence class permitted to make a future candidate-specific disambiguation attempt eligible;
- eligibility is **not** a resolved decision;
- `STRUCTURAL`, `BASS_INVERSION`, `VERIFIED_NCT`, `COLOR_TONE`, `ADJACENT_CONTEXT`, and `VOICE_FUNCTION` do not independently authorize a sixth-vs-seventh root choice;
- written pitch spelling does not solve the collision because both interpretations share the same spelled note set in ordinary notation;
- AI/model output cannot authorize or override the deterministic choice.

A future runtime promotion requires a separate deterministic, candidate-specific tonal-context rule, calibration-only development, regression evidence, and final untouched HOLDOUT validation.

## Teacher-Gold impact

After vocabulary v0.2, complete `7sus2/7sus4` cases are executable, while the remaining reference-only cases are sixth-chord collision cases. Current frozen 200-case coverage is 184 executable / 16 reference-only = 92.0%.

This coverage statement is a post-validation measurement only. HOLDOUT musical cases must not be converted into special-case rules or regression fixtures.

## Non-goals

This contract does not:

- create a sixth-chord candidate producer;
- add `6` or `m6` to authoritative runtime vocabulary;
- change resolver precedence;
- change confidence/abstention behavior;
- alter public API schemas;
- grant AI/model authority;
- authorize Stage 8/model training or production promotion.
