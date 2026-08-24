# Public spelling-aware request contract v1.1

## Purpose

`public_request` v1.1 is an additive transport/validation contract for trustworthy symbolic sources such as MusicXML-derived guitar notation. It carries optional written pitch spelling into the existing deterministic core without changing harmonic authority.

The frozen `public_request` v1.0 contract remains unchanged and MIDI-only.

## Versioning

- schema name: `st_guitar_harmonic_engine.public_request`
- legacy request version: `1.0`
- spelling-aware request version: `1.1`
- public result version: unchanged `1.0`

v1.0 and v1.1 are validated by separate entrypoints. v1.0 does not silently accept v1.1 event fields.

## Event shape

Every v1.1 event has the v1.0 fields plus an explicit `written_pitch` field:

```json
{
  "staff": 1,
  "voice": 1,
  "midi_pitch": 50,
  "onset": {"numerator": 0, "denominator": 1},
  "duration": {"numerator": 1, "denominator": 1},
  "tie": "none",
  "written_pitch": {"step": "D", "alter": 0, "octave": 3}
}
```

When source spelling is unavailable, `written_pitch` must be explicitly `null`. Missing fields are rejected. The spelling object accepts:

- `step`: `A` through `G`
- `alter`: integer `-2..2`
- `octave`: integer `-1..9`

Unknown fields, booleans in integer fields, unsupported steps, and out-of-range values fail closed.

## Reuse of the v1.0 security boundary

v1.1 removes only the additive spelling field and re-runs the complete v1.0 validator before attaching spelling to canonical core events. Existing bounds remain authoritative:

- maximum frames
- maximum events per frame
- maximum total events
- beat numerator/denominator bounds
- MIDI bounds
- timing/frame constraints
- duplicate event/frame rejection
- phrase-plan validation
- enum validation
- canonical frame/event ordering

This avoids maintaining a second independent implementation of the established untrusted-input boundary.

## Harmonic authority

Written spelling is not a chord label and does not create a candidate by itself. It can only support the already-implemented fail-closed symmetric-root rule for exact augmented or diminished-seventh ties.

If spelling is missing, partial, pitch-class-inconsistent, conflicting, or otherwise unsafe, the spelling evidence is ignored and the existing deterministic ambiguity behavior remains.

The contract does not:

- change evidence precedence;
- change resolver vocabulary;
- change confidence semantics;
- bypass ambiguity or abstention;
- consult AI/model output;
- authorize Stage 8 or model promotion.

## Execution

`validate_public_request_v1_1(payload)` returns the same `ValidatedPublicRequest` core type used by v1.0. `execute_public_request_v1_1(payload)` delegates to the existing deterministic runtime and serializes the unchanged public result v1.0 envelope.

## Benchmark discipline

The v1.1 transport contract is developed against generic synthetic cases and calibration-safe examples. Teacher-Gold HOLDOUT is not used to tune this contract. Existing holdout results must not be converted into test fixtures or resolver-specific exceptions.
