# Stage 8 OpenScore Metadata-Only Mining Runner v0.1

Status: local research infrastructure only. This runner cannot authorize model training or production authority.

## Purpose

Execute the already-frozen OpenScore symbolic path locally after conversion:

`conversion receipt manifest -> integrity-bound .mxl -> MusicXML intake -> deterministic ambiguity miner -> metadata-only JSONL`

The runner deliberately does **not** download OpenScore repositories and does **not** invoke MuseScore. Snapshot materialization and `.mscx -> .mxl` conversion remain separate boundaries.

## Required inputs

- an absolute path to a local JSON conversion-receipt manifest;
- the expected SHA-256 of that exact manifest file;
- an absolute local root containing previously converted `.mxl` files;
- the exact deterministic engine commit SHA;
- a new absolute output path outside the MXL root.

The runner refuses to overwrite output.

## Frozen manifest schema

Top-level fields are exactly:

```json
{
  "schema": "st_guitar_harmonic_engine.stage8_openscore_mining_manifest",
  "version": "0.1",
  "item_count": 1,
  "items": []
}
```

Each item contains exactly the persisted fields of a successful `OpenScoreConversionReceipt`:

- `source_id`
- `snapshot_commit_sha`
- `score_relative_path`
- `source_sha256`
- `output_relative_path`
- `output_sha256`
- `output_bytes`
- `rootfile_path`
- `executable_sha256`
- `executable_version`
- `exit_code`

No label, preferred candidate, Teacher-Gold field, model result, training flag, or raw score payload is accepted in the manifest.

## Revalidation

The runner does not trust reconstructed receipt metadata blindly. It rechecks:

- manifest SHA-256 against the caller-pinned digest;
- source IDs against the approved OpenScore sources;
- snapshot SHAs against the frozen snapshot contract;
- canonical `scores/**/*.mscx` and corresponding `.mxl` paths;
- duplicate source/output entries;
- MXL root containment and symlink traversal;
- `META-INF/container.xml` rootfile identity against the receipt;
- MXL byte size and SHA-256 through the MusicXML intake;
- deterministic engine SHA format.

The existing MusicXML intake additionally enforces bounded ZIP/XML structure and rejects DTD/entity declarations, malformed archives, unsupported pitch/timing constructs, and receipt drift.

## Output

The output is canonical JSONL and contains metadata only.

Line 1 is a run record containing:

- schema/version/miner version;
- manifest SHA-256;
- deterministic engine SHA;
- source item count;
- harmonic frame count;
- ambiguous candidate count;
- candidate-pool SHA-256;
- `model_training_authorized = false`;
- `production_authority_granted = false`.

Remaining lines are DRAFT ambiguity candidates containing provenance, source-group identity, frame/candidate fingerprints, deterministic candidate IDs, and at most four previous-frame fingerprints.

The output does not contain MIDI event lists, written-pitch event lists, MusicXML, `.mscx` payloads, lyrics, OpenScore automatic analyses, audio, PDFs, Teacher-Gold/HOLDOUT labels, or human answers.

## Causality

Candidate mining remains exactly the Stage 8 OpenScore Ambiguity Miner v0.1 contract:

- final state must be `AMBIGUOUS`;
- no future frame is used;
- at most four previous-frame fingerprints are emitted as later context metadata;
- the miner never selects a preferred candidate.

## Bounds

- manifest: <= 8 MiB;
- manifest items: <= 10,000;
- mined candidates: <= 50,000;
- metadata output: <= 128 MiB.

Any bound violation blocks the run.

## Atomic publication

The complete JSONL payload is written to a temporary file in the output directory, flushed and fsynced, then published with a no-overwrite hard-link operation. Existing output causes a fail-closed error.

## CLI

```bash
python -m st_guitar_harmonic_engine.stage8_openscore_mining_runner \
  --manifest /private/openscore-conversion-manifest-v0.1.json \
  --manifest-sha256 <64hex> \
  --mxl-root /private/openscore-mxl \
  --engine-commit-sha <40hex> \
  --output-jsonl /private/openscore-sc-candidates-v0.1.jsonl
```

Exit `0` means the metadata pool was produced and is ready for later human review. Exit `2` means a safety/integrity gate blocked the run.

`READY_FOR_HUMAN_REVIEW` is **not** model-training authorization.

## Non-goals

v0.1 does not:

- clone/download OpenScore;
- convert `.mscx` files;
- assign TRAIN / VALIDATION / SC-HOLDOUT splits;
- assign final `SC-*` IDs;
- perform human musical adjudication;
- choose preferred candidates;
- extract model features;
- train/evaluate a model;
- tune thresholds;
- alter deterministic resolver behavior;
- grant advisory or production promotion.
