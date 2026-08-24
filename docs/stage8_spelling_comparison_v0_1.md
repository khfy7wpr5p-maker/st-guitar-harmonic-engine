# Stage 8 spelling-aware comparison v0.1

This is a non-authoritative comparison profile over the frozen Teacher-Gold partitions.
It does **not** replace the Stage 8-0 public-v1.0 baseline and does not authorize model
training, model promotion, threshold tuning, or resolver changes.

Profile: `public_v1_1_spelling`

The profile rebuilds each already-validated Teacher-Gold v0.1 single-frame request as
public request v1.1 by preserving the written spelling carried by `input_notes`. The
request then runs through the existing deterministic runtime. Each case is executed
twice and checked for schema compatibility and byte-canonical determinism.

Safety invariants:

- frozen calibration/holdout namespace and v0.3 vocabulary guards are reused;
- DRAFT rows fail closed;
- HOLDOUT is measured only and is never used for tuning;
- public v1.0 remains the Stage 8-0 baseline profile;
- spelling is evidence only and cannot bypass evidence precedence, ambiguity, or
  abstention contracts;
- no AI/model component is called;
- comparison accuracy is descriptive and creates no production authority.

The profile exists because MIDI-only v1.0 intentionally loses enharmonic spelling,
while augmented triads and fully diminished sevenths can require validated written
spelling to choose one root safely. This comparison measures that already-existing
deterministic capability separately rather than attributing such corrections to a
future model.
