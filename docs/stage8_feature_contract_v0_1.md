# Stage 8-B Causal Feature Contract v0.1

Status: feature-schema contract only. No extraction, model training, model selection, or production authority.

Target: `sequence-context-ambiguity-shadow-v1`.

## Allowed feature families

Current frame:
- pitch-class mask;
- bass pitch class;
- note count.

Current deterministic candidate:
- root pitch class;
- family;
- variant;
- current-frame-safe evidence flags: exact, tonal-context, structural, bass-inversion, verified-NCT, incomplete-chord, color-tone.

Explicit current context:
- tonic pitch class;
- tonal mode.

Causal sequence context:
- previous deterministic state;
- previous resolved identity fields when available;
- previous bass pitch class;
- lookback limited to 1..4 frames.

Phrase metadata:
- current phrase position index only.

## Explicitly forbidden

- future/next-frame features;
- phrase length, because it can encode future knowledge;
- current `ADJACENT_CONTEXT` and `VOICE_FUNCTION` evidence surfaces, because existing deterministic annotations may inspect the next frame;
- Teacher-Gold labels;
- frozen HOLDOUT labels;
- expected/target answers;
- teacher reasons or arbitrary raw text;
- any feature not present in the explicit whitelist.

The feature schema must be frozen before any later training plan. A frozen schema is not model-training authorization.

## Authority boundary

The future research component may only rank the immutable candidate set already emitted by the deterministic engine for an `AMBIGUOUS` frame. Feature extraction must not generate candidates or modify the authoritative resolver state.
