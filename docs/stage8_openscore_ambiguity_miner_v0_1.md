# Stage 8 OpenScore Ambiguity Miner v0.1

Status: research-infrastructure only. This contract cannot authorize model training or production authority.

## Purpose

Mine human-review candidates from frozen OpenScore symbolic scores by reusing the existing deterministic harmonic engine and retaining only frames whose final abstention-gated state is `AMBIGUOUS`.

The miner is intentionally metadata-only. It does not choose a preferred harmonic identity and does not consume external harmonic labels.

## Allowed inputs

- `ParsedOpenScoreScore` produced by the bounded Stage 8 MusicXML intake.
- Exact deterministic engine commit SHA.
- Frozen OpenScore String Quartets or OpenScore Lieder snapshots already accepted by the Stage 8 provenance contract.

## Prohibited inputs

The miner must not consume:

- OpenScore automatic harmonic analyses (`analysis_automatic.rntxt`),
- lyrics or textual semantic content,
- Teacher-Gold rows or Teacher-Gold HOLDOUT labels,
- SC-HOLDOUT labels,
- model outputs,
- future frames,
- inferred target labels.

## Decision boundary

For each harmonic frame:

1. call the existing `aggregate_frame_evidence(frame, None)`;
2. call the existing `resolve_candidates_by_precedence`;
3. call the existing `apply_abstention_policy`;
4. retain the frame only if the final state is `AMBIGUOUS`.

`RESOLVED`, `ABSTAIN`, and `NO_MATCH` frames are discarded from the SC candidate pool.

No phrase plan, adjacency annotator, voice-function annotator, inferred key, or future-frame context is allowed in v0.1 mining decisions.

## Causal context metadata

A retained candidate may include SHA-256 fingerprints for at most four immediately preceding harmonic frames. These fingerprints are metadata for later human review and feature construction only; they cannot affect whether the current frame is mined.

The current frame fingerprint is never included in `previous_frame_sha256`, and no future frame fingerprint is emitted.

## Candidate identity

Candidate identities are canonical tokens:

`pc:<root_pc>:<family>:<variant>`

The set is sorted, unique, contains at least two candidates, and is bound by a deterministic SHA-256 `candidate_set_sha256`.

The miner never removes an authoritative candidate and never adds a model-generated candidate.

## Source grouping / split leakage

- String Quartets are grouped at the enclosing work/set directory.
- Lieder are conservatively grouped at the composer/set (cycle) level.

The derived `source_group_id` is stable and is intended for later TRAIN / VALIDATION / SC-HOLDOUT split-disjointness checks.

## Human-review state

Every mined candidate enters review with:

- `preferred_candidate_id = None`
- `annotation_status = "draft"`
- `model_training_authorized = False`
- `production_authority_granted = False`

A later human adjudication step may choose one existing candidate or explicit `no_preference` under the already-frozen SC corpus contracts. Mining itself cannot perform that adjudication.

## Output boundary

The miner emits metadata/fingerprints and candidate identities. It does not write raw OpenScore score payloads, MusicXML, audio, PDF, automatic analyses, or lyrics into the project repository.

## Security invariants

Fail closed on:

- unapproved source IDs or unsafe score paths,
- malformed engine SHA,
- malformed source/group/candidate hashes,
- non-canonical or duplicate candidate identities,
- attempts to inject a preferred candidate or verified annotation state,
- attempts to grant training or production authority.

## Non-goals

v0.1 does not:

- download OpenScore repositories,
- run MuseScore conversion,
- select TRAIN/VALIDATION/HOLDOUT partitions,
- perform human musical adjudication,
- train or evaluate a model,
- tune thresholds,
- alter deterministic resolver behavior,
- grant advisory or production promotion.
