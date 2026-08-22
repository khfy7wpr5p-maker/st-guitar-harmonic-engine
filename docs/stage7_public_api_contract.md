# Stage 7 Public API Safety Contract

Schema: `st_guitar_harmonic_engine.public_request` v1.0

The public API accepts JSON-compatible untrusted input and validates it before conversion into core domain types. The boundary is framework-independent and contains no network, filesystem, subprocess, parser-SDK, UI, or AI types.

## Authority

Public/API input is not authoritative. Harmonic authority remains:

UNTRUSTED INPUT -> VALIDATION/NORMALIZATION -> BOUNDED EVIDENCE -> DETERMINISTIC HARMONIC POLICY -> AUTHORITATIVE RESOLVER -> CONFIDENCE/AMBIGUITY/ABSTENTION -> FINAL RESULT

The API layer may validate, normalize, canonicalize, serialize, and invoke existing deterministic core behavior. It may not invent a harmonic identity, bypass resolver precedence, convert categorical confidence into probability, or allow AI evidence to mutate authoritative state.

## Validation

Requests are fail-closed for unsupported schema names/versions, unknown modes/enums, malformed objects, extra/missing fields, invalid MIDI pitches, invalid rational beats, impossible frame boundaries, invalid event durations, duplicate events/frames, invalid phrase spans, and bounded-size violations.

Current safety bounds are contract limits, not musical claims: maximum 512 frames, maximum 64 events per frame, maximum 8192 total events, and bounded rational numerator/denominator values.

## Determinism and serialization

Equivalent accepted payloads are normalized into canonical core objects. Public result serialization is versioned and deterministic. Confidence remains categorical evidence strength. No probability or blind weighted score is exposed.

## Backward compatibility

This is an additive public API surface. Existing explainability schema v1.x and existing core domain contracts are not replaced or modified. Existing Stage 1-6 callers can continue using the prior Python core API.
