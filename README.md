# ST Guitar Harmonic Engine

A safety-first symbolic harmony engine for polyphonic guitar scores.

## Stage 0-A: deterministic core foundation

The repository currently establishes only the trusted symbolic event boundary.
It does **not** infer chords yet.

### Current contract

- exact musical timing via reduced rational values (no floating-point beat math),
- validated `NoteEvent` identifiers and MIDI pitch range,
- explicit tie state,
- deterministic event end calculation,
- no network, model, training, or runtime service dependency.

Later stages will add versioned score/measure contracts, harmonic frames, chord
candidate generation, deterministic resolution, and optional specialist models.
AI output will remain advisory to the final resolver rather than silently
changing this core contract.

## Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```
