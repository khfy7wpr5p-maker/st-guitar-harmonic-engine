# Stage 2-N — Runtime Frame Identity Bridge

## Purpose

Stage 2-M established that Function training must remain on HOLD until a Stage2G
Function event can be joined to the exact deterministic runtime frame without
heuristics. Stage 2-N adds the engine-side half of that bridge.

The bridge creates a stable `runtime_frame_id` from:

1. the SHA-256 digest of the immutable symbolic source presented to the runtime
   adapter, and
2. the exact current `HarmonicFrame` content already validated by the engine:
   measure number, exact frame start/end, and canonicalized active note events
   (staff, voice, MIDI pitch, exact onset, exact duration, tie state).

The hash uses canonical JSON and SHA-256. The source digest prevents equal-looking
frames in different works from colliding.

## Safety boundary

`runtime_frame_id` is a **join key, not a model feature**.

The bridge does not contain or consume:

- harmonic decisions, Function/Roman/Key targets, teacher labels, or expected answers;
- next/future-frame context;
- inferred timing, duration, segment boundaries, or nearest-event matching;
- AI/model scores;
- production authority.

The deterministic resolver remains authoritative and the existing public request
schema is unchanged. Stage 2-N is a sidecar identity contract only.

## Source digest rule

`source_sha256` must be the SHA-256 digest of the immutable symbolic source bytes
used by the adapter that produced the runtime frames. It must not be a filename,
path, request correlation id, teacher label, or model-derived value.

## Trace contract

`build_runtime_frame_identity_trace()` accepts only a `ValidatedPublicRequest` and
emits a decision-free sidecar with:

- source SHA-256;
- canonical frame index;
- `runtime_frame_id`;
- measure number;
- exact current frame start/end;
- explicit false authority/leakage flags.

Duplicate identities in one validated request fail closed.

## What Stage 2-N proves

A PASS proves that the deterministic engine has a stable, source-scoped identity
for its actual runtime frames.

A PASS does **not** prove that the Stage2G private Function events can already
reproduce those identities. Function final training therefore remains HOLD.

## Next safe step

Stage 2-O belongs in `st-guitar-harmonic-ai-training`: a TRAIN-only source adapter
must reopen the exact Stage2G source material, construct engine-equivalent frames
from source-grounded symbolic data, compute the same `runtime_frame_id`, and audit
exact event-to-frame joins.

Any Stage2G event that cannot be matched exactly must remain unmatched/quarantined.
No nearest-frame, order-only, inferred-onset, inferred-duration, or label-assisted
recovery is allowed.
