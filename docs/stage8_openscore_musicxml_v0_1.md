# Stage 8 OpenScore MusicXML intake v0.1

Purpose: consume one integrity-bound `.mxl` conversion receipt and map its symbolic score into the engine's existing `Measure`, `NoteEvent`, `RationalBeat`, `TieState`, and `WrittenPitch` contracts. This layer performs no harmony inference and creates no training labels.

## Trust boundary

The parser requires an `OpenScoreConversionReceipt` and an absolute local MXL path. Before XML parsing it rechecks:

- MXL regular-file status;
- exact compressed byte size from the receipt;
- exact MXL SHA-256 from the receipt;
- ZIP structure and bounded archive entry count;
- normalized archive member paths;
- no encrypted members;
- bounded total uncompressed size;
- presence and bounded size of the receipt-declared MusicXML rootfile;
- no `DOCTYPE` or entity declarations.

The MXL archive is read in place; it is never extracted to the filesystem.

## Supported MusicXML v0.1 surface

- `score-partwise` only;
- up to 32 parts and 5,000 measures per part;
- exact integer `divisions` timing;
- inherited/simple time signatures;
- `note`, `chord`, `rest`, `backup`, and `forward` timing semantics;
- numeric voices and staves within bounded ranges;
- pitched A..G notes with integer alter `-2..2`;
- written spelling preserved as `WrittenPitch`;
- sounding MIDI derived from written pitch plus explicit MusicXML `transpose` chromatic/octave-change;
- MusicXML tie `start`/`stop` mapped to engine `TieState`;
- pickup/irregular measure duration preserved through `actual_duration`.

Grace, cue, and unpitched notes do not become harmonic `NoteEvent` values in this v0.1 intake. Their presence does not authorize guessed pitch content.

## Fail-closed cases

The whole score is rejected rather than guessed when the parser encounters, among other things:

- malformed XML;
- `score-timewise` or unknown score root;
- missing/duplicate part IDs;
- part measure-count or measure-label misalignment;
- conflicting part time signatures;
- timing before `divisions`/time definition;
- negative cursor after `backup`;
- unsupported/microtonal alters;
- invalid pitch/voice/staff/transposition bounds;
- event-count overflow;
- source/MXL receipt hash drift.

## Measure identity

The engine's current `Measure` contract requires positive integer measure numbers. OpenScore source measure labels are therefore preserved separately in `source_measure_labels`, while engine measures use deterministic ordinal numbers `1..N`. No source label is silently coerced into an integer identity.

## Authority boundary

The returned object contains symbolic note evidence only. It does not:

- resolve harmony;
- select an ambiguous candidate;
- read Teacher-Gold/HOLDOUT labels;
- extract Stage 8 features;
- authorize model training;
- grant production authority.

`model_training_authorized=false` and `production_authority_granted=false` remain invariant.

## Next stage

A separate ambiguity miner will:

1. build existing harmonic frames from these measures;
2. run existing deterministic evidence aggregation/resolver/abstention logic;
3. retain only final `AMBIGUOUS` frames;
4. attach at most four **previous** frame fingerprints as causal context;
5. emit metadata-only SC candidate records with no preferred label.
