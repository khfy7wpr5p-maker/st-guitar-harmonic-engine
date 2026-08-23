# ST Guitar Harmonic Engine — Stage 7 Architecture Freeze

Stage 7 freezes the production-facing contracts without promoting any AI model or changing the deterministic harmonic authority model.

## Authoritative core boundary

The frozen authority path is:

`UNTRUSTED INPUT -> VALIDATION / NORMALIZATION -> BOUNDED EVIDENCE -> DETERMINISTIC HARMONIC POLICY -> AUTHORITATIVE RESOLVER -> CONFIDENCE / AMBIGUITY / ABSTENTION -> FINAL RESULT`

Only the deterministic resolver may produce the authoritative harmonic identity. Exact validated harmony remains highest precedence. Ambiguity must remain explicit when equally strong candidates cannot be safely distinguished. Weak or insufficient single-candidate evidence is withheld by the abstention gate.

## Frozen evidence precedence

1. exact validated harmony
2. explicit tonal context
3. structural continuity / harmonic boundary
4. bass / inversion
5. verified NCT
6. incomplete chord / omission
7. extension / suspended / altered color evidence
8. previous / next harmonic context
9. voice-leading / functional evidence

This is lexicographic evidence precedence, not a blind weighted score.

## AI boundary

AI evidence schema v1.0 is advisory and bounded. The shadow audit schema v1.0 names `deterministic_resolver` as authoritative source. Timeout, exception, empty response, unavailable model, malformed payload, unsupported specialist/schema/model, stale or conflicting evidence must collapse to no accepted AI evidence. AI evidence, reranking, confidence or disagreement audit may not replace or mutate the deterministic decision.

No model promotion is authorized by this freeze.

## Guitar evidence boundary

Guitar voicing schema v1.0 is descriptive bounded evidence, not harmonic authority. String/fret/TAB data, open strings, bass position, inversion possibilities and pitch duplication may describe a voicing but may not create harmonic identity directly. Pitch-class identity remains separate from occurrence count so doubling cannot amplify evidence strength.

## Ambiguity and abstention

Final states remain `resolved`, `ambiguous`, `abstain`, and `no_match`. `BASS_INVERSION` alone remains weak and abstained. Omission-only evidence remains weak unless independently corroborated under the frozen deterministic policy. Exact ties remain ambiguous unless a higher permitted deterministic context rule safely distinguishes them.

Post-freeze Teacher-Gold maintenance permits one narrowly documented structural exact-tie rule: a symmetric `augmented` or `diminished_seventh` exact tie may be narrowed when a normalized symbolic source supplies complete, pitch-class-consistent, non-conflicting written spelling and exactly one candidate matches the written tertian letter stack. This does not change evidence precedence, does not permit arbitrary `EXACT + STRUCTURAL` tie-breaking, and fails closed to ambiguity when spelling is missing, inconsistent, non-unique, or conflicts with a unique tonal-context choice. See `symmetric_root_spelling_evidence_v0_1.md`.

Post-freeze Teacher-Gold maintenance also permits the abstention gate to withhold an authoritative ambiguous set when every surviving candidate is weak/insufficient `INCOMPLETE_CHORD` evidence. The source ambiguity and all candidates remain visible; this is not candidate resolution.

## Serialization and public API

- Explainability schema remains v1.x compatible and non-authoritative; v1.0 is the frozen base.
- Public request schema: `st_guitar_harmonic_engine.public_request` v1.0.
- Public result schema: `st_guitar_harmonic_engine.public_result` v1.0.
- Public input is validated and bounded before conversion to core domain objects.
- Batch mode resolves frames independently; sequence mode uses the existing deterministic sequence resolver and only explicitly validated phrase context.
- Serialization is canonical, deterministic and versioned.
- Confidence remains categorical and must not be presented as probability.
- Public request v1.0 remains MIDI-only; written-spelling evidence is not silently added to that schema.

## Audit and benchmark

- AI shadow audit remains v1.0 and non-authoritative.
- Benchmark interface remains v1.0.
- Without teacher-gold, the benchmark may report resolver behavior/stability rates but must state musical accuracy as unavailable.
- Performance profiling remains `diagnostic_only`; latency/memory measurements may never alter resolver semantics or confidence gates.

## Differential regression

Stage 6 final main `c2df9d09d3e2c84a9ea203f8567ec5e48eeab3ea` remains the frozen pre-Stage-7 semantic reference for exact resolution, ambiguity, abstention, precedence and determinism. Any intentional change requires an explicit documented contract revision and cannot be treated as an optimization or incidental refactor.

The Teacher-Gold maintenance changes above are explicit contract revisions: complete-base extension/altered evidence may add bounded structural support; all-weak incomplete ambiguity may be withheld as abstention; and symmetric exact root ambiguity may use fail-closed written-spelling structural evidence. None changes AI authority or evidence precedence.

## Security debts outside engine semantics

Repository branch protection remains an external repository-settings debt. Internal merge discipline therefore continues to require feature branches, CI PASS, pre-merge fresh-read and expected-head merge checks. GitHub Actions are pinned to immutable SHAs and run with read-only contents permission.

## Post-freeze boundary

Stage 7-H does not authorize Stage 8, real-model production promotion, probability calibration, or musical-accuracy claims. Those require a separate decision and, where applicable, teacher-gold/adjudicated benchmark evidence.
