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

### Stage 0-C — polyphonic harmonic frames ✅

- exact frame boundaries from note onsets/ends,
- active-note sets remain constant inside each frame,
- silent gaps are not fabricated as harmony,
- canonical pitch-class evidence is exposed without naming chords.

### Stage 1-A — exact chord candidates ✅

- deterministic basic triad/seventh templates,
- exact pitch-class matching only,
- octave duplicates do not distort the candidate set,
- symmetric sonorities retain all valid roots instead of forcing a guess.

### Stage 1-B — bass and inversion ✅

- literal lowest sounding MIDI pitch is the bass evidence,
- candidate-relative root/first/second/third inversion,
- candidate/frame evidence mismatch is rejected,
- no contextual reinterpretation of the bass is performed.

### Stage 1-C — exact analysis orchestration ✅

- frame → candidates → bass/inversion wired end-to-end,
- deterministic `UNIQUE`, `AMBIGUOUS`, or `NO_MATCH` status,
- ambiguity is preserved rather than silently resolved,
- empty/silent measures return no fabricated result.

### Stage 1-D — written pitch spelling contract ✅

- optional A–G written step + accidental + octave is preserved,
- written spelling remains separate from canonical sounding MIDI,
- guitar octave transposition is never guessed from MIDI alone,
- later key/context logic can use enharmonic evidence without changing exact analysis.

### Stage 1-E — tonal context resolver ✅

- caller supplies explicit tonic pitch class and major/minor mode,
- exact candidates are annotated with conservative scale-degree/role evidence,
- tonal context may narrow exact ambiguity only when it provides a defensible match,
- unsupported or chromatic evidence is preserved rather than rejected or guessed,
- minor-key major V and raised-leading-tone diminished harmony are supported explicitly.

### Stage 1-F — conservative NCT and omission evidence ✅

- passing and neighbor tones require the same unique exact chord on both sides,
- the middle frame may add exactly one pitch class and must show stepwise motion in one voice,
- incomplete-chord inference is limited to an omitted perfect fifth,
- only major/minor triads and major/minor/dominant sevenths are eligible for fifth omission,
- exact matches always outrank incomplete inference,
- these evidence layers do not mutate or override exact/context resolver results.

### Stage 1-G — explainability-only evidence aggregation ✅

- frame-level reports expose NCT observations and fifth-omission candidates,
- explainability output contains no authoritative decision or selection field,
- exact `UNIQUE/AMBIGUOUS/NO_MATCH` results remain owned by the exact analyzer,
- tonal-context `RESOLVED/AMBIGUOUS/NO_MATCH` results remain owned by the context resolver,
- building an explainability report cannot mutate or override either decision path.

### Stage 1-H — versioned explainability schema contract ✅

- explainability JSON-compatible output is identified by schema name and version `1.0`,
- rational musical time remains exact as `{numerator, denominator}` rather than float,
- required v1 fields for frames, NCT evidence, and fifth-omission evidence are frozen,
- `1.x` changes are additive-only and unknown additive fields are tolerated by v1 readers,
- removing or changing required v1 fields requires a new major schema version,
- decision-bearing fields remain forbidden from the explainability schema.

### Stage 2-A — harmonic boundary / structural segmentation ✅

- canonical frame boundaries are candidate transition points, not automatic harmonic boundaries,
- fixed rule priority distinguishes `BOUNDARY`, `CONTINUATION`, and `UNRESOLVED`,
- silence and different unique exact harmonies create boundaries,
- verified passing/neighbor tones and one exact anchor plus one uniquely matching missing-fifth frame may continue a segment,
- ambiguous or insufficient evidence is never silently merged; `UNRESOLVED` cuts the segment,
- inversion, octave, voice, or staff changes do not create a boundary by themselves,
- existing exact/context decision paths are not mutated by structural segmentation,
- schema `1.0` serialization remains unchanged by default; optional structural evidence is an additive `1.1` extension with no authoritative decision fields.

### Stage 2-B — conservative suspension evidence ✅

- suspension detection is evidence-only and does not alter structural or harmonic decisions,
- preparation and resolution frames must be temporally contiguous and uniquely exact,
- preparation and resolution harmonies must differ,
- the middle frame must replace exactly one target chord pitch class with one prepared foreign pitch class,
- the same staff/voice must sustain the prepared pitch or carry an explicit tie chain,
- resolution must occur in the same staff/voice, to the missing target pitch class, downward by semitone or whole tone,
- ambiguous anchors, unprepared tones, silent gaps, upward motion, and leaps are rejected rather than guessed.

### Stage 2-C — conservative anticipation evidence ✅

- anticipation detection is evidence-only and cannot alter harmonic or structural decisions,
- source and arrival frames must be temporally contiguous and uniquely exact,
- source and arrival harmonies must differ,
- the middle frame must replace exactly one source-harmony pitch class with one future chord tone,
- the anticipated tone must belong to the following harmony but not the source harmony,
- exactly one event may carry the anticipated pitch and it must begin at the middle-frame boundary,
- the same staff/voice and MIDI pitch must continue into the arrival frame by one spanning event or an explicit tie chain,
- unrelated rearticulation, silent gaps, ambiguous anchors, and multi-foreign-tone cases are rejected rather than guessed.

### Stage 2-D — conservative appoggiatura / escape-tone evidence ✅

- ornamental NCT detection is evidence-only and cannot alter any existing decision path,
- previous and following frames must be contiguous and carry the same unique exact harmony,
- a middle frame with its own exact chord interpretation is never reclassified as ornament,
- the middle frame must substitute exactly one anchor pitch class with one foreign pitch class,
- one unambiguous staff/voice event must occupy exactly the middle frame,
- appoggiatura requires leap-in plus opposite-direction semitone/whole-tone resolution,
- escape tone requires semitone/whole-tone approach plus opposite-direction leap-out,
- changed/ambiguous anchors, multiple foreign tones, ties, and unsupported motion remain unresolved.

### Stage 2-E — conservative sustained-pedal evidence ✅

- pedal detection is evidence-only and cannot alter exact, contextual, structural, or prior NCT decisions,
- one physical `NoteEvent` must remain active across at least three consecutive, contiguous harmonic frames,
- explicit tie chains and rearticulated notes are not merged into one pedal at this stage,
- the candidate event is removed hypothetically and every reduced frame must resolve to one unique exact harmony,
- the underlying harmony must change across the sustained span,
- the sustained pitch must be a chord tone in at least one underlying harmony and a non-chord tone in at least one other,
- unchanged harmony, all-chord-tone common tones, all-foreign drones, silent/reduced-empty cases, and ambiguous reduced harmony are rejected rather than guessed.

### Stage 2-F — broader one-tone omission evidence ✅

- the Stage 1-F fifth-only API remains intact and deterministic,
- a new evidence-only generator covers exactly one missing root, third, fifth, or seventh,
- support remains limited to major/minor triads and major/minor/dominant sevenths,
- exact chord matches suppress every incomplete interpretation,
- incomplete ambiguity is preserved by returning all matching candidates without ranking,
- diminished, augmented, half-diminished, diminished-seventh, altered, extension, or multi-tone omissions are still rejected.

Altered or diminished-fifth omissions, extensions, modulation, beat-strength weighting,
cadential inference, progression probabilities, confidence ranking, and AI boundary models
remain deliberately unresolved.

## Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```
