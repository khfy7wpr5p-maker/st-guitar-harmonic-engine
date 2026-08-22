# Stage 7-A/B/C Shadow Review

- New public API module is additive and framework-independent.
- No network, filesystem, subprocess, parser-SDK, UI, or AI dependency is introduced.
- External payloads are validated before core domain construction.
- Unsupported schema versions, malformed payloads, invalid enum values, invalid pitches/durations/boundaries, duplicates, and oversized inputs fail closed.
- Public serialization reports the existing deterministic gated decision and does not create a competing authority path.
- Confidence remains categorical evidence strength and is not exposed as probability.
- Existing resolver precedence, exact/context behavior, ambiguity, abstention, and explainability schema v1.x are unchanged.
- Merge is permitted only after Python 3.11/3.12/3.13 CI passes and pre-merge main/head verification succeeds.
