# Stage 8 Sequence / Context Research Corpus Contract v0.1

Status: metadata/readiness contract only. No raw score/audio content, model training, or production authority.

## Namespace

Future research cases use a separate `SC-00001...` namespace. They must not reuse Teacher-Gold or frozen HOLDOUT rows.

## Case requirements

Each case binds:
- approved Stage 8 target ID;
- TRAIN or VALIDATION split;
- source/source-group identity;
- source-item SHA-256;
- deterministic candidate-set SHA-256;
- the immutable deterministic candidate IDs;
- current Stage 8-B feature-contract version;
- deterministic engine commit SHA;
- rights-governance state;
- human annotation state.

No raw score, audio, teacher prose, or copyrighted source payload belongs in this public metadata contract.

## Human adjudication

A `VERIFIED` case must have exactly one of:
- one preferred candidate that is already present in the deterministic candidate set; or
- explicit `no_preference=True` when musical evidence remains genuinely ambiguous.

The contract never forces a musical preference. DRAFT rows are not corpus-ready.

## Leakage controls

- Teacher-Gold overlap: forbidden;
- HOLDOUT overlap: forbidden;
- HOLDOUT-derived target/labels: forbidden;
- the same source group cannot appear in both TRAIN and VALIDATION;
- duplicate case IDs or duplicate source-item snapshots are forbidden;
- both TRAIN and VALIDATION partitions must exist;
- rights/data governance must already have passed.

## Authority boundary

`CORPUS_DESIGN_READY` means only that metadata, split isolation, rights, and human-verification states are structurally ready. It does not authorize model training or production use.

Actual musical adjudication is a human-review step and remains outside autonomous development authority.
