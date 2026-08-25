# Stage 8 OpenScore MuseScore conversion boundary v0.1

Purpose: locally convert one already-materialized, hash-bound OpenScore `.mscx` score to one `.mxl` artifact without weakening source, filesystem, archive, or model-authority boundaries.

## Input contract

A request must bind:

- approved OpenScore `source_id`;
- exact frozen repository commit from `stage8_openscore_snapshot.py`;
- absolute and disjoint input/output roots;
- normalized `scores/**/*.mscx` relative path;
- source file SHA-256;
- absolute MuseScore executable path;
- MuseScore executable SHA-256 and bounded version text;
- bounded timeout and output sizes.

The converter verifies the source file and executable hashes before execution. Source symlinks are rejected. Input and output roots cannot contain each other.

## Execution

The adapter invokes MuseScore with an argument vector equivalent to:

```text
<MuseScore executable> -o <controlled output.mxl> <controlled input.mscx>
```

`subprocess` is called with `shell=False`. No command string is assembled and no shell expansion, wildcard, arbitrary output extension, or overwrite is permitted.

The official MuseScore command-line interface documents `-o/--export-to` converter mode. The pinned OpenScore repositories also document bulk MuseScore CLI conversion, and OpenScore Lieder supplies `corpus_conversion.json` for `.mscx` → `.mxl` jobs. This adapter deliberately uses one score per invocation so every source/output pair receives an individual receipt.

## Output validation

A zero process exit code is not enough. The `.mxl` output must additionally:

- exist as a regular, non-symlink file;
- be non-empty and below the configured compressed-size bound;
- be a valid ZIP/MXL archive;
- contain no unsafe `..`/absolute archive members;
- contain no encrypted members;
- stay below entry-count and total uncompressed-size bounds;
- contain exactly one rootfile declaration in `META-INF/container.xml`;
- point to an existing `.xml` or `.musicxml` member.

The output is not extracted by this stage.

## Receipt

A successful conversion returns metadata only:

- source ID and frozen source commit;
- score-relative path;
- source SHA-256;
- output-relative path, SHA-256, and size;
- MXL rootfile path;
- MuseScore executable SHA-256/version;
- zero exit code.

The receipt carries no raw score content, labels, Teacher-Gold data, model features, or harmonic answer.

`model_training_authorized=false` and `production_authority_granted=false` are invariants.

## Out of scope

- network download/clone;
- raw OpenScore payload commits;
- MusicXML parsing;
- harmonic-frame extraction;
- ambiguity mining;
- human annotation;
- feature extraction or model training;
- threshold tuning or authoritative AI.
