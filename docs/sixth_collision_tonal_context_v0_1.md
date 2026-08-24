# Sixth collision tonal-context disambiguation v0.1

## Purpose

This contract allows explicit caller-supplied tonic/mode context to narrow an already-preserved sixth/seventh exact collision. It does not create collisions, infer keys, score probabilities, or consult model output.

## Eligible collision pairs

- major sixth ↔ relative minor seventh
- minor sixth ↔ relative half-diminished seventh

The collision must already satisfy the runtime safety contract and root-position seventh guard.

## Candidate-specific rule

Exactly one collision candidate may receive `TONAL_CONTEXT` only under these narrow rules:

- `major_sixth`: its root equals the explicit tonic and the explicit mode is major;
- `minor_sixth`: its root equals the explicit tonic and the explicit mode is minor;
- competing `minor_seventh`: its root equals the explicit tonic and the explicit mode is minor.

A competing `half_diminished_seventh` is not treated as a tonic by this collision rule.

If none of these rules matches, the two exact candidates remain equal and the resolver preserves `AMBIGUOUS`.

## Examples

For the pitch set C–E–G–A with C in the bass:

- no context → `C6 | Am7/C` remains ambiguous;
- C major → `C6` receives `TONAL_CONTEXT` and resolves;
- A minor → `Am7/C` receives `TONAL_CONTEXT` and resolves;
- C minor or unrelated tonic → ambiguity remains.

For C–Eb–G–A with C in the bass:

- C minor → `Cm6` resolves;
- A minor does not auto-promote `Am7b5/C`; ambiguity remains.

## Invariants

This contract does not change:

- evidence precedence;
- the exact collision generator;
- root-position seventh protection;
- public request/result schemas;
- confidence or abstention policy;
- Teacher-Gold data or frozen labels;
- AI/model authority;
- Stage 8 authorization.

The tonic/mode must be explicit trusted deterministic input. No inferred key, statistical preference, bass preference, spelling preference, adjacency, voice-leading, or model output may substitute for it.
