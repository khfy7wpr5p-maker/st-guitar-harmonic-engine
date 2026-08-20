# ST Guitar Harmonic Engine

A safety-first symbolic harmony engine for polyphonic guitar scores.

## Current foundation

### Stage 0-A — deterministic event core ✅

- exact timing with reduced rational values,
- validated `NoteEvent` identifiers and MIDI pitch range,
- explicit tie state,
- no AI/model/network dependency.

### Stage 0-B — measure and meter contracts

- all timing is explicitly defined in quarter-note units,
- validated time signatures with exact nominal measure length,
- explicit realized duration for pickup/irregular measures,
- event-to-measure ownership and overflow validation,
- canonical event ordering for repeatable downstream analysis.

The engine still does **not** infer chords. Harmony inference begins only after
its symbolic boundaries are versioned and regression-tested.

## Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```
