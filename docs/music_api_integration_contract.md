# Music API + ST Harmonic Engine Integration Contract

Status: integration boundary v1.0

## Goal

Expose the existing ST Guitar Harmonic Engine to a Music API transport without
moving harmonic authority into the transport, provider SDK, model output, or UI.

The integration path is:

```text
Music API / HTTP / client
        |
        v
provider or transport adapter
(auth, HTTP, retries, rate limits, provider payload mapping)
        |
        v
music_api_bridge v1.0
(strict envelope, request correlation, version dispatch)
        |
        v
ST public_request v1.0 / v1.1 / v1.2
(strict validation + canonicalization)
        |
        v
deterministic harmonic runtime
        |
        v
resolved | ambiguous | abstain | no_match
```

## Authority rule

The transport is never harmonic authority.

A Music API implementation may:

- authenticate clients;
- apply rate limits and request-size limits before the core boundary;
- map a provider-specific request into a supported ST public request;
- forward an opaque bounded request id for correlation;
- serialize the returned ST result;
- map transport failures to transport-specific status codes.

A Music API implementation must not:

- inject a provider chord label into the nested ST request;
- inject provider confidence, probability, ranking, or model score into the
  authoritative resolver;
- convert `ambiguous`, `abstain`, or `no_match` into `resolved`;
- guess missing written pitch, timing, voice, tie, tonal context, or phrase data;
- bypass versioned ST validation;
- mutate evidence precedence or abstention policy;
- add HTTP/SDK concerns to the deterministic public runtime.

## Bridge request schema v1.0

```json
{
  "schema_name": "st_guitar_harmonic_engine.music_api_bridge",
  "schema_version": "1.0",
  "request_id": "client-request-123",
  "harmonic_request": {
    "schema_name": "st_guitar_harmonic_engine.public_request",
    "schema_version": "1.2",
    "mode": "batch",
    "frames": [],
    "phrase_spans": null,
    "tonal_context_spans": null
  }
}
```

The example shows the envelope only. `frames` must satisfy the existing public
request contract and therefore cannot actually be empty in an executable
request.

Supported nested request versions are currently 1.0, 1.1, and 1.2. The bridge
dispatches to the corresponding existing deterministic executor. It does not
translate between public schema versions.

## Bridge response schema v1.0

```json
{
  "schema_name": "st_guitar_harmonic_engine.music_api_result",
  "schema_version": "1.0",
  "request_id": "client-request-123",
  "harmonic_result": {
    "schema_name": "st_guitar_harmonic_engine.public_result",
    "schema_version": "1.0",
    "results": []
  }
}
```

The nested result remains the frozen ST public result. The bridge does not add a
probability or provider score.

## Provider-neutral implementation rule

`st_guitar_harmonic_engine.music_api_bridge` is transport-neutral and must stay
free of:

- HTTP clients or servers;
- API keys or secret handling;
- provider SDKs;
- retry/backoff code;
- filesystem or subprocess access;
- UI types;
- AI/model inference.

Those concerns belong in an outer service/adapter. This keeps the harmonic
package deterministic, testable, and reusable from CLI, web service, desktop,
and future gateway environments.

## Provider adapter responsibilities

A concrete provider adapter should implement these steps in order:

1. Parse and authenticate the provider request outside the harmonic core.
2. Reject unsupported transport/media types before mapping.
3. Map only source-grounded symbolic music fields to an ST public request.
4. Use v1.1 when written pitch spelling is available; use `null` when it is not.
5. Use v1.2 tonal context only when the caller supplied explicit bounded context;
   never estimate a key inside the bridge.
6. Wrap the request in the bridge v1.0 envelope.
7. Call `execute_music_api_bridge_request`.
8. Preserve the ST decision state exactly in the outward response.

## Failure behavior

The boundary is fail-closed.

- Invalid bridge envelopes raise `MusicApiBridgeValidationError`.
- Invalid nested ST requests continue to raise the existing
  `PublicValidationError`.
- Unsupported nested schema versions are rejected before execution.
- Provider-specific extra authority fields are not silently ignored.

A network service may map validation errors to a 4xx response, but it must not
recover by inventing musical data.

## Next integration stage

The next stage is a thin network shell around this bridge. It should be developed
separately from the deterministic core boundary and should include authentication,
rate limiting, request body limits, timeout/cancellation handling, health/readiness,
and contract tests. A provider SDK should be added only after a specific Music API
provider is selected and its license, data model, authentication, and failure
semantics are reviewed.
