# Stage 8 private baseline runner v0.1

This runner is the private execution boundary for the Stage 8-0 deterministic
baseline seal. It keeps frozen Teacher-Gold rows out of the public repository.

## Command

```bash
python -m st_guitar_harmonic_engine.stage8_baseline_runner \
  --calibration-csv /private/TEACHER_GOLD_CALIBRATION_V0.1_FROZEN.csv \
  --holdout-csv /private/TEACHER_GOLD_HOLDOUT_V0.1_FROZEN.csv \
  --engine-commit-sha <40-hex-engine-commit> \
  --output-json /private/stage8-baseline-seal.json
```

## Fail-closed input rules

- each CSV must be a regular UTF-8 file;
- maximum size is 256 KiB per partition;
- exact eight-column Teacher-Gold v0.1 header/order is required;
- exactly 100 rows are required in each partition;
- all rows must pass the existing VERIFIED Teacher-Gold reference adapter;
- calibration and holdout IDs must match their frozen namespaces;
- source SHA-256 values must differ;
- an existing output file is never overwritten.

## Execution

The runner:

1. hashes the exact frozen CSV bytes;
2. adapts rows through Teacher-Gold vocabulary v0.3;
3. assembles the frozen 100 + 100 benchmark with existing partition guards;
4. executes the existing deterministic Teacher-Gold evaluator;
5. builds the Stage 8-0 self-hashing baseline seal;
6. atomically writes only the seal JSON.

The seal contains aggregate/split metrics and source fingerprints. It does not
contain `input_notes`, `teacher_reason`, human row text, or model output.

## Runtime contract

v0.1 of this runner intentionally evaluates the frozen public request/runtime v1.0
path used by the existing `TeacherGoldEvaluationReport`. Spelling-aware public v1.1
and explicit tonal-context v1.2 can be measured as separately named comparison
profiles, but must not silently replace the baseline execution profile.

This keeps the Stage 8 entry baseline reproducible and prevents later model work
from redefining which deterministic runtime was measured.

## Exit status

- `0`: seal status is `READY`;
- `2`: seal was produced but is `BLOCKED`;
- validation or file errors fail with a non-zero exception exit.

`READY` remains an integrity/determinism statement, not a model-training or model-
promotion authorization.
