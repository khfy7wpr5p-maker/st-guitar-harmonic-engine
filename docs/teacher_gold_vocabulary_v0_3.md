# Teacher-Gold vocabulary mapping v0.3

## Purpose

Teacher-Gold vocabulary v0.3 is an additive compatibility layer over frozen v0.1 and v0.2. It promotes major-sixth and minor-sixth human labels only after the deterministic runtime gained an explicit collision-preserving representation for sixth/seventh equal pitch sets.

## Newly representable labels

v0.3 adds:

- `6` → `CandidateFamily.BASIC / major_sixth`
- `m6` → `CandidateFamily.BASIC / minor_sixth`

Slash-bass text remains review metadata and does not change root identity.

## Safety model

Representability does not imply automatic resolution.

The runtime may expose a sixth identity only through the sixth-collision contract. When a sixth pitch set collides with a relative minor seventh or half-diminished seventh and root-position seventh protection does not apply, both identities remain explicit candidates and the resolver preserves ambiguity.

Examples:

- `C6 | Am7/C`
- `Dm6 | Bm7b5/D`

A root-position exact seventh such as `A–C–E–G = Am7` remains protected and is not automatically expanded into a sixth alternative.

## Frozen compatibility

v0.3 does not modify:

- Teacher-Gold v0.1 adapters/reference truth;
- Teacher-Gold v0.2 suspended-seventh mappings;
- calibration or HOLDOUT rows;
- public request/result schemas;
- evidence precedence;
- confidence or abstention policy;
- AI/model authority;
- Stage 8 authorization.

The v0.3 benchmark assembly wrapper upgrades representability metadata and then reuses all existing frozen 100+100 partition, case-id, split, ordering, partial-alternative, and readiness guards.
