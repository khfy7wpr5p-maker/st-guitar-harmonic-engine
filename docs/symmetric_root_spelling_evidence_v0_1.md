# Symmetric Root Written-Spelling Evidence v0.1

## Purpose

Augmented triads and fully diminished seventh chords are symmetric in sounding pitch-class space. MIDI pitch classes alone therefore retain multiple exact roots. When a normalized symbolic source already preserves written pitch spelling, that spelling can provide deterministic structural evidence without guessing from sound alone.

This post-freeze maintenance contract is intentionally narrow.

## Supported scope

Written spelling may narrow an exact tie only when all of the following hold:

1. the exact candidate set contains at least two candidates;
2. every exact candidate is `BASIC` and has the same variant;
3. that variant is exactly `augmented` or `diminished_seventh`;
4. every sounding event carries a `WrittenPitch`;
5. each written pitch class agrees with the sounding MIDI pitch class;
6. repeated occurrences of one sounding pitch class do not carry conflicting enharmonic spellings;
7. exactly one exact candidate matches the written tertian letter stack.

The matching candidate receives `STRUCTURAL` evidence in addition to its existing exact evidence. All exact candidates remain present in the evidence pool.

## Fail-closed behavior

No root is narrowed when:

- written spelling is missing or partial;
- written and sounding pitch classes disagree;
- duplicate sounding pitches carry conflicting enharmonic spellings;
- more than one written-stack interpretation survives;
- the exact tie is not a supported symmetric quality;
- structural spelling evidence conflicts with a unique tonal-context choice.

In each of those cases, the existing exact ambiguity remains authoritative.

## Public API boundary

`public_request` schema v1.0 remains unchanged and still carries sounding MIDI only. This PR does not add `written_pitch` to public request v1.0 and therefore does not silently change external request compatibility.

The new evidence is available only to core paths that already receive normalized `NoteEvent.written_pitch` values from a trustworthy symbolic source or a dedicated benchmark/core adapter. A future public spelling-aware boundary would require an explicit versioned contract.

## Authority and safety

- no new candidate identity is invented;
- no exact candidate is deleted by the aggregator;
- arbitrary `EXACT + STRUCTURAL` markers cannot break non-symmetric exact ties;
- exact evidence remains highest precedence;
- tonal-vs-spelling conflict remains ambiguous;
- no weighted scoring;
- no AI/model authority;
- no HOLDOUT-derived tuning;
- no Stage 8 authorization.
