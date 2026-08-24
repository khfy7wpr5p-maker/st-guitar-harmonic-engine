# Public tonal-context request v1.2

## Purpose

Public request v1.2 is an additive deterministic transport contract for caller-supplied tonal context. It layers `tonal_context_spans` on top of the spelling-aware v1.1 request without changing v1.0 or v1.1.

The engine does not infer keys or modulations at this boundary.

## Schema delta

v1.2 keeps the v1.1 fields and adds exactly one required outer field:

- `tonal_context_spans`: `null` or a list of explicit context spans.

Each span contains exactly:

- `start_index`
- `end_index`
- `tonic_pc`
- `mode`

`tonic_pc` is bounded to 0..11. `mode` is `major` or `minor`. Spans are half-open `[start_index, end_index)`, must be non-empty, cannot overlap, and cannot extend beyond the canonical frame count.

As with existing phrase spans, indexes refer to the canonicalized frame order produced by the public validator.

## Validation inheritance

The v1.2 validator removes only the additive context field, changes the internal validation version to v1.1, and reuses the complete v1.1 validation path. Therefore all existing limits and checks remain in force, including:

- exact outer/frame/event fields;
- frame/event count limits;
- timing bounds;
- duplicate rejection;
- canonical frame/event ordering;
- spelling validation;
- phrase-plan validation;
- batch/sequence mode rules.

v1.0 and v1.1 remain strict and do not silently accept the v1.2 outer shape.

## Runtime use

Validated context spans become an existing `LocalTonalContextPlan` and are passed to the deterministic evidence aggregator / sequence resolver.

This makes the sixth-collision tonal-context contract externally usable while adding no new evidence source or resolver authority.

If context is absent or irrelevant, existing ambiguity/abstention behavior is preserved.

## Output compatibility

Execution still emits frozen `st_guitar_harmonic_engine.public_result` schema version `1.0`.

## Non-goals

v1.2 does not:

- infer tonic or mode;
- infer modulation boundaries;
- use probabilities or model output;
- change evidence precedence;
- change confidence or abstention policy;
- modify Teacher-Gold rows;
- authorize Stage 8/model promotion.
