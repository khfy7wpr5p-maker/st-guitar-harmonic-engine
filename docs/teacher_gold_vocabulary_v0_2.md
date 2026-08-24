# Teacher-Gold vocabulary mapping v0.2

## Purpose

The frozen Teacher-Gold reference vocabulary v0.1 remains unchanged for reproducibility. Vocabulary mapping v0.2 is an additive compatibility layer that attaches engine identities only to teacher labels the deterministic runtime can now represent safely.

## Newly representable labels

v0.2 promotes:

- `7sus2`
- `7sus4`

Slash-bass notation is accepted as review metadata and does not change harmonic root identity, consistent with the existing Teacher-Gold adapter convention.

These labels map to `CandidateFamily.SUSPENDED` with variants `7sus2` and `7sus4`, exactly matching the deterministic runtime vocabulary introduced independently before this mapping layer.

## Frozen v0.1 preservation

The existing v0.1 adapter and reference contract are not modified. A v0.1 `C7sus4` reference therefore remains reference-only when read through the v0.1 entrypoint. Applying `upgrade_reference_case_v0_2` attaches the new engine identity without changing:

- case id;
- split;
- expected state;
- exact teacher label;
- public request payload;
- inversion metadata;
- teacher reason.

This makes the vocabulary transition explicit and reversible.

## Sixth-chord boundary

`6` and `m6` remain reference-only.

Reason:

- a major-sixth pitch set is identical to the relative minor-seventh pitch set;
- a minor-sixth pitch set is identical to a relative half-diminished-seventh pitch set.

Therefore note content alone cannot safely decide a sixth-chord root. Promoting these labels without explicit higher evidence would violate the ambiguity/abstention contract. A separate collision contract must be established before any runtime sixth-chord promotion.

## Benchmark use

Existing frozen reference cases may be upgraded with `upgrade_reference_cases_v0_2` before being passed into the existing benchmark assembly. The assembly itself does not need a semantic change because it already accepts any fully representable `TeacherGoldReferenceCase` and refuses partially representable cases.

HOLDOUT cases must not be converted into special-case rules or regression fixtures. The mapping is label-generic and derives only from the independently implemented runtime vocabulary.

## Non-goals

v0.2 does not:

- mutate frozen v0.1 data or adapters;
- add sixth-chord runtime authority;
- change resolver precedence;
- change confidence or abstention policy;
- change public API schemas;
- consult AI/model output;
- authorize Stage 8/model promotion.
