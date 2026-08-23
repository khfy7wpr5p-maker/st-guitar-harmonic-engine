# Weak Incomplete Ambiguity Abstention v0.1

## Purpose

Teacher-Gold calibration showed a decision-policy mismatch where multiple incomplete-chord hypotheses could survive the authoritative resolver even though every surviving hypothesis was supported only by weak omission evidence. Reporting such a set as a meaningful harmonic ambiguity overstates the available evidence.

This maintenance gate preserves the Stage 3 source decision and all candidates, but changes the final state to `ABSTAIN` when every authoritative candidate:

1. carries `INCOMPLETE_CHORD` evidence; and
2. remains `WEAK` or `INSUFFICIENT` under the existing strength contract.

The explicit abstention reason is:

`ambiguous_weak_incomplete`

## Preserved behavior

The following remain `AMBIGUOUS`:

- exact conflicts;
- structural/contextual bounded ambiguities;
- suspended/color-tone ambiguities;
- incomplete-chord ambiguities where independent corroboration raises any surviving candidate above weak evidence.

## Audit semantics

For weak incomplete ambiguity abstention:

- `source_status` remains `ambiguous`;
- all source candidates remain visible;
- no primary candidate is chosen;
- no single-candidate confidence is claimed;
- the underlying ambiguity reason remains visible;
- final state is `abstain` with `ambiguous_weak_incomplete`.

## Safety invariants

- no candidate invention or deletion;
- no resolver precedence change;
- no exact ambiguity suppression;
- no generic ambiguity-to-abstain conversion;
- no AI/model authority;
- no HOLDOUT-derived tuning;
- no Stage 8 authorization.
