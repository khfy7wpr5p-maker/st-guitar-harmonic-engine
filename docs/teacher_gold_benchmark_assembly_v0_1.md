# Teacher-Gold Benchmark Assembly v0.1

## Scope

This contract joins the frozen Teacher-Gold calibration partition (`TG-0001..TG-0100`) and the frozen untouched holdout partition (`TG-0101..TG-0200`) without changing authoritative harmonic resolution, confidence, abstention, public runtime, AI/model authority, or production behavior.

The assembly layer consumes already validated `TeacherGoldReferenceCase` values only. It does not read Google Sheets, files, network resources, or model outputs.

## Frozen partition requirements

The v0.1 assembly fails closed unless both exact namespaces are present in canonical order:

- calibration: 100 reference cases, `TG-0001..TG-0100`, all carrying `BenchmarkSplit.CALIBRATION`;
- holdout: 100 reference cases, `TG-0101..TG-0200`, all carrying `BenchmarkSplit.HOLDOUT`.

Wrong counts, wrong split tags, reordered/missing IDs, or namespace contamination are rejected.

## Reference truth vs engine-executable truth

Human reference truth remains the complete 200-case source of evaluation truth.

A case enters `TeacherGoldBenchmark` only when the current frozen engine vocabulary can represent the **entire** human truth for that case. If any accepted human candidate has no `HarmonicIdentity`, the whole case remains reference-only. The assembly never scores only the representable half of an ambiguous case.

Likewise, if two distinct human alternatives collapse onto one engine identity, that case remains reference-only because current engine vocabulary cannot faithfully express the distinction.

`ABSTAIN` and `NO_MATCH` cases remain executable without candidate identities because their expected state intentionally carries zero identities.

## Readiness semantics

`TeacherGoldBenchmarkAssembly.readiness` delegates to the existing `calibration_readiness()` contract.

`BENCHMARK_READY` means only:

1. exact frozen calibration and holdout reference partitions are present; and
2. the safely executable benchmark contains cases from both splits.

It does **not** mean:

- every one of the 200 human reference cases is engine-representable;
- current resolver vocabulary is complete;
- empirical accuracy has already been measured;
- confidence is probabilistically calibrated;
- Stage 8/model training is authorized;
- AI/model output may mutate authoritative harmony state;
- runtime or production promotion is approved.

Reference-only cases remain explicitly listed in `reference_only_case_ids` and are preserved in `reference_cases`.

## Safety invariants

- no Sheet or network I/O;
- no resolver mutation;
- no evidence-precedence change;
- no confidence/ambiguity/abstention change;
- no public API change;
- no AI/model authority;
- no partial-case scoring;
- deterministic canonical ordering;
- calibration and holdout namespaces remain disjoint.

## Next gate

After a real frozen 200-case reference manifest is assembled, the next permitted action is deterministic benchmark execution and reporting against the current frozen engine. That evaluation is evidence gathering only and does not itself authorize Stage 8/model training or production promotion.
