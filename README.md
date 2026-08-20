# ST Guitar Harmonic Engine

A safety-first symbolic harmony engine for polyphonic guitar scores.

## Current foundation

### Stage 0-A — deterministic event core ✅

- exact timing with reduced rational values,
- validated `NoteEvent` identifiers and MIDI pitch range,
- explicit tie state,
- no AI/model/network dependency.

### Stage 0-B — measure and meter contracts ✅

- all timing is explicitly defined in quarter-note units,
- validated time signatures with exact nominal measure length,
- explicit realized duration for pickup/irregular measures,
- event-to-measure ownership and overflow validation,
- canonical event ordering for repeatable downstream analysis.

### Stage 0-C — polyphonic harmonic frames

- exact frame boundaries from note onsets/ends,
- active-note sets remain constant inside each frame,
- silent gaps are not fabricated as harmony,
- canonical pitch-class evidence is exposed without naming chords.

The engine still does **not** infer chord labels; Stage 0-C only produces trusted
simultaneous-note evidence for later candidate generation.

## Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```
