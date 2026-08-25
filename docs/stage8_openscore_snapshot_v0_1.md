# Stage 8 OpenScore snapshot contract v0.1

Status: provenance/source-design contract only. It does not download data, parse scores, mine labels, start model training, or grant model authority.

## Frozen external snapshots

The following repositories were live-read before this contract was created and are pinned by exact commit SHA:

| source_id | repository | commit | license | license blob | score root | source | conversion target |
|---|---|---|---|---|---|---|---|
| `openscore-string-quartets` | `OpenScore/StringQuartets` | `91c780acf1502e7b4f745dc100836c501f41d8e3` | `CC0-1.0` | `0e259d42c996742e9e3cba14c677129b2c1b6311` | `scores/` | `.mscx` | `.mxl` |
| `openscore-lieder` | `OpenScore/Lieder` | `6b2dc542ce2e8aa4b78c8ee62103b210efc07015` | `CC0-1.0` | `0e259d42c996742e9e3cba14c677129b2c1b6311` | `scores/` | `.mscx` | `.mxl` |

Both repositories carry the same CC0 1.0 `LICENSE.txt` blob at these snapshots. Their READMEs describe MuseScore-format score sources and command-line/batch conversion to MusicXML/MXL. The Lieder repository explicitly documents `mscore -j corpus_conversion.json` for `.mscx` → `.mxl` conversion.

## Security and provenance rules

- Never follow moving `main` when producing research data. Materialization must use the exact pinned commit.
- A repository commit, license blob, source path, or license change is metadata drift and requires a new reviewed snapshot version.
- Raw score payloads are not committed to this repository.
- Materialized local files must receive separate SHA-256 content fingerprints before entering any research manifest.
- Source work/group identity must later be preserved so TRAIN, VALIDATION, and untouched SC-HOLDOUT stay disjoint.
- Only `.mscx` sources under `scores/` are in scope for this v0.1 conversion boundary.
- Conversion output is `.mxl`; PDF/MP3/OMR is outside this path.
- This contract records source eligibility only. `model_training_authorized=false` and `production_authority_granted=false` remain invariant.

## External evidence recorded at freeze time

- OpenScore String Quartets README: collection in MuseScore format; bulk conversion through MuseScore desktop/CLI; scores released under CC0.
- OpenScore Lieder README: collection in MuseScore format; `corpus_conversion.json` supports bulk `.mscx` → `.mxl`; scores released under CC0.
- Both repository `LICENSE.txt` files are CC0 1.0 Universal at the pinned snapshots.

## Next boundary

A separate conversion contract will govern a local, non-networked execution step:

`pinned .mscx source → MuseScore executable → .mxl → content hash + conversion receipt`

That step must validate executable identity/version, bounded input/output paths, source extension, exit status, output existence, output size, and output SHA-256. It still will not perform harmonic mining or model training.
