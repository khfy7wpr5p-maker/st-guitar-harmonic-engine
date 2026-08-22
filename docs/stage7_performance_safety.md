# Stage 7-G Performance Safety

Performance measurements are diagnostic only. They are forbidden from changing resolver precedence, candidate identity, confidence, ambiguity, abstention, or AI authority.

The profiling surface measures batch/sequence latency, retained traced-memory delta, peak traced bytes, and output stability across repeated executions. No latency or memory threshold is a musical decision gate.

Pathological or oversized input must pass the existing public validation boundary before any profiling work starts. Invalid input therefore fails closed using the same public schema and bounded-size rules.

Optimization work must preserve the frozen Stage 6 differential semantics and Stage 7 public serialization contract. A faster result with different harmonic semantics is a regression, not an optimization.
