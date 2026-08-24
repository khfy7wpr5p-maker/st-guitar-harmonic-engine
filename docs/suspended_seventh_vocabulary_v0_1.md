# Suspended-seventh vocabulary v0.1

## Scope

This change adds deterministic runtime representation for complete `7sus2` and `7sus4` sonorities without changing the frozen basic exact-chord vocabulary.

Supported pitch-set templates are:

- `7sus2`: root, major second, perfect fifth, minor seventh (`0, 2, 7, 10`)
- `7sus4`: root, perfect fourth, perfect fifth, minor seventh (`0, 5, 7, 10`)

## Safety boundary

The existing exact basic-chord layer remains higher precedence. If a pitch set is already an exact basic triad/seventh match, suspended inference is suppressed exactly as before.

Suspended triads remain `COLOR_TONE`-only evidence because their three-note pitch sets preserve dual-root ambiguity (`sus2` / `sus4`).

Complete suspended sevenths receive `STRUCTURAL + COLOR_TONE` because:

1. all four structural tones are present;
2. no omission is inferred;
3. the supported 7sus2/7sus4 pitch sets have one unique root/kind mapping under transposition;
4. no existing basic exact seventh template has the same pitch set.

This produces bounded deterministic resolution for a complete suspended seventh while preserving ambiguity for suspended triads.

## Non-goals

This change does not:

- add sixth chords;
- infer incomplete suspended sevenths;
- alter exact-basic precedence;
- change confidence semantics;
- change public request/result schemas;
- use AI/model evidence;
- use Teacher-Gold HOLDOUT as a tuning source;
- authorize Stage 8/model promotion.

Teacher-Gold adapter/reference mapping is intentionally left unchanged in this PR and must be aligned only after this runtime vocabulary passes CI independently.
