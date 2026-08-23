# Teacher-Gold Deterministic Evaluation v0.1

## Purpose

This layer measures agreement between frozen human Teacher-Gold reference truth and the current deterministic public runtime. It is evidence gathering only.

It does not modify the authoritative resolver, evidence precedence, confidence, ambiguity, abstention, public runtime, AI/model authority, or production behavior. It does not authorize Stage 8/model training.

## Evaluation population

The complete frozen reference corpus remains the source of truth. Cases that the current frozen `HarmonicIdentity` vocabulary cannot fully represent remain explicit `reference-only` cases and are not executed or partially scored.

The accuracy denominator is therefore:

`engine_executable_cases_only`

Reference-only cases are excluded from the numeric accuracy denominator rather than being counted as either correct or incorrect. Their IDs remain in the report so coverage is visible.

Execution/validation failures for an otherwise engine-executable case remain inside that denominator and therefore count against musical accuracy.

## Correctness rule

For every executable case the runtime is executed twice.

A case is correct only when:

1. both outputs satisfy public result schema v1.0;
2. both outputs are byte-canonically deterministic;
3. final decision state matches Teacher-Gold; and
4. when identity is applicable, the complete canonical identity set matches Teacher-Gold.

`RESOLVED` and `AMBIGUOUS` require both state and exact identity-set agreement.

`ABSTAIN` and `NO_MATCH` intentionally contain zero Teacher-Gold identities and are scored by final state only.

A partially representable ambiguity is never scored using only its representable candidate.

## Determinism and failure isolation

Each executable case is evaluated twice using the same public request. Canonical JSON bytes must match.

A nondeterministic result is recorded as `NondeterministicOutput` for that case. Validation/runtime exceptions are isolated per case so one failure does not abort evaluation of the remaining corpus.

## Reported metrics

- reference case count;
- executable case count;
- reference-only case count;
- executable coverage;
- musical accuracy over executable cases;
- final-state accuracy;
- identity accuracy where identity comparison applies;
- validation/runtime error count;
- corpus-level deterministic-stability flag;
- per-case expected/actual state, identity-match status, schema/determinism status and output SHA-256.

## Explicit limitation: inversion and spelling

Public result schema v1.0 serializes harmonic identity as `root_pc`, `family`, and `variant`. It does not serialize Teacher-Gold inversion or original written spelling.

Therefore v0.1 reports:

`inversion_accuracy_claim = not_available_public_result_v1_0`

No inversion-accuracy number may be inferred from this evaluator. Enharmonic spelling distinctions that were used for human adjudication also cannot be reconstructed from the MIDI-only public request boundary.

## Security and authority invariants

- no Google Sheet or network I/O in the evaluator;
- no source Teacher-Gold rows committed to the public repository;
- no resolver mutation;
- no new harmonic identity authority;
- no evidence-precedence change;
- no confidence/ambiguity/abstention change;
- no AI/model invocation;
- no training or production promotion;
- no partial-case scoring;
- deterministic repeated execution;
- failures remain explicit rather than silently dropped.

## Readiness meaning

A green evaluator contract means the repository can deterministically measure the current frozen engine against a separately supplied frozen Teacher-Gold assembly.

It does not itself prove a musical accuracy value. A real accuracy claim requires an actual private evaluation run using the frozen calibration and holdout snapshots.
