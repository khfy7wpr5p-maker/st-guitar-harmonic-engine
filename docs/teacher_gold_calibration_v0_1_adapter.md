# Teacher Gold calibration Sheet v0.1 adapter

This adapter is a bounded, non-authoritative bridge from the frozen eight-column
Teacher Gold calibration Sheet into the existing Stage 4-G `TeacherGoldCase`
contract and Stage 7 public request schema.

## Safety boundary

- No Google Drive, network, file, subprocess, or model access is performed.
- Only rows with `annotation_status=VERIFIED` are accepted.
- Sheet columns must match v0.1 exactly.
- `ABSTAIN` and `NO_MATCH` rows may not claim candidate identities.
- `AMBIGUOUS` rows must preserve at least two representable identities.
- Unsupported human chord labels fail closed; they are never coerced into a
  different engine identity.
- The adapter does not change resolver precedence, confidence, abstention,
  ambiguity, or any other authoritative harmonic decision.

## Public request conversion

Each `input_notes` value is converted deterministically from scientific pitch
notation to one simultaneous batch frame. The generated payload is passed
through the existing public-request validator before it is returned.

The conversion preserves sounding MIDI pitch but the current public request
schema does not carry written/enharmonic spelling. `expected_inversion` and
`teacher_reason` are retained as review metadata by `AdaptedTeacherGoldCase`;
the current `TeacherGoldCase` contract does not score inversion.

## Current vocabulary boundary

The adapter maps only identities already representable by the frozen engine
families:

- basic triads and seventh chords,
- natural 9/11/13 extension identities already supported by the engine,
- sus2/sus4 triads,
- dominant b9/#9/#11/b13 altered identities.

Musically valid teacher labels such as sixth chords (`C6`, `Dm6`) and suspended
seventh chords (`C7sus4`) remain unsupported by the current `HarmonicIdentity`
contract and are reported as validation failures. This is intentional evidence
of a schema/vocabulary gap, not a reason to modify teacher-gold labels.

## Frozen snapshot validation

`validate_frozen_calibration_v0_1()` additionally checks the exact 100-row
`TG-0001` through `TG-0100` snapshot shape. A frozen snapshot can be considered
adapter-compatible only when that report is fully valid.

This module does not authorize Stage 8, AI/model promotion, or any musical
accuracy claim.
