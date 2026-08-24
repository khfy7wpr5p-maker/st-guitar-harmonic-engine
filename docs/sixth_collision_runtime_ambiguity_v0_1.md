# Sixth collision runtime ambiguity v0.1

## Purpose

This contract makes equal-pitch-set sixth/seventh collisions visible to the authoritative deterministic resolver without allowing a sixth chord to be inferred independently.

Supported collision pairs:

- major sixth ↔ relative minor seventh
- minor sixth ↔ relative half-diminished seventh

Examples:

- C6 = C–E–G–A = Am7/C as a pitch-class set
- Cm6 = C–Eb–G–A = Am7b5/C as a pitch-class set

## Fail-closed generation rule

A sixth candidate is added only when all of the following are true:

1. the frozen exact analyzer has already produced exactly one exact candidate;
2. that candidate is `minor_seventh` or `half_diminished_seventh`;
3. the inverse sixth-root collision derived from the safety contract reproduces the observed pitch-class set exactly;
4. no independent sixth inference, heuristic, model output, spelling preference, or bass preference is used.

The sixth identity is represented in the existing `CandidateFamily.BASIC` family with variant `major_sixth` or `minor_sixth`.

## Authority behavior

Both collision candidates carry equal `EXACT` and `BASS_INVERSION` evidence. Therefore the Stage 3 precedence resolver must preserve `AMBIGUOUS` rather than selecting one root.

Explicit tonal context is intentionally withheld from collision candidates in this version. This prevents the existing seventh-only context rules from accidentally choosing the seventh candidate before a separate candidate-specific sixth-context contract exists.

## Non-collision invariants

This change does not modify:

- major/minor triads;
- dominant, major, minor, half-diminished, or diminished sevenths outside an equal sixth collision;
- suspended, extension, altered, omission, NCT, adjacency, or voice-leading producers;
- evidence precedence;
- confidence or abstention policy;
- public request/result schemas;
- Teacher-Gold labels or frozen data;
- AI/model authority;
- Stage 8 authorization.

## Next gate

A later contract may attach candidate-specific `TONAL_CONTEXT` evidence to exactly one collision candidate when explicit tonic/mode evidence is sufficient. Until then, collision pitch sets remain authoritative ambiguity.
