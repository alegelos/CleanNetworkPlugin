---
name: androidcleannetwork
description: Create or update Kotlin endpoint integrations using AndroidCleanNetwork, including domain contracts, Setup and Provider types, request DTOs, response mapping, JSON fixtures and tests. Use when an Android app or SDK consumes AndroidCleanNetwork or the user requests an integration with it; not for unrelated networking libraries or general SDK maintenance.
metadata:
  api-baseline: "1.0.1"
---

# AndroidCleanNetwork integration

Implement the consumer's feature against its actual SDK version and established
architecture. The SDK provides transport and testing building blocks; the
feature's Setup, Provider, Domain types, codec and spies belong to the consumer.

## Establish the integration

1. Inspect resolved dependencies and existing providers. The reference describes
   the SDK's locally declared version 1.0.1, not a guaranteed published Maven
   release. Reuse an existing dependency and check the installed interfaces.
2. Read [the integration guide](references/integration.md) and the relevant
   files in the [executable User example](assets/UserExample/). The example is
   a reference, not a reason to replace an existing project's architecture.
3. Establish method, path, base URL, query/body contract, response shape and
   authentication from the supplied API documentation. Ask for missing facts
   that change behavior; a successful JSON sample does not prove optionality,
   a nullable field's non-null type or an authentication refresh design.

## Apply the pattern

- Domain interfaces accept and return Domain values. Keep transport request
  `*DTO`, response `*Response` and `.domain` mapping in Data, with `*Setup` and
  `*Provider`. Preserve deliberate equivalent host conventions.
- Group related endpoints in one sealed Setup and provider when appropriate.
  A bodyless GET needs no request DTO. Add only files relevant to the feature.
- Implement the six `ApiSetupProtocol` properties. Use `ApiRequestBuilder`
  for URLs and query parameters; read the guide's path-encoding rules before
  interpolating identifiers. Only GET, POST, PUT and PATCH exist in `HttpMethod`.
- Inject `NetworkSessionProtocol` and call `session.dataFor(setup)`. This keeps
  the real provider usable with `DefaultNetworkSession` or a fixture session.
  `ApiProvider` is optional configuration, not a concrete client or superclass.
- Encode a request DTO before constructing the Setup and propagate codec errors.
  The SDK transports bytes and supplies no JSON codec. Reuse the host's codec;
  the sample uses kotlinx.serialization as a consumer dependency.
- Decode the response and map to Domain in the provider. Respect required and
  optional fields from the API contract; do not invent fallback values or return
  an empty collection on malformed JSON. Preserve coroutine cancellation.
- Add the token refresh helper only when the app/API needs it and supplies an
  `ApisGatewayProtocol`. The application owns tokens and refresh coordination.

## Verify the integration

- Test the production provider with `MockedNetworkSession`, a test-owned resolver
  for its real Setup, and JSON under `src/test/resources`. Fixture names include
  the relative classpath path and `.json`, for example `fixtures/GetUser.json`.
  Supply a class from the test target as `fixtureAnchor`. Kotlin does not need
  the Swift example's test-only protocol conformance or Bundle configuration.
- Test requests separately: URLs, query parameters, methods, headers and decoded
  JSON bodies. Android's fixture session evaluates `setup.request` for its URL,
  but does not assert request contents or simulate HTTP status errors.
- Use the real OkHttp adapter with MockWebServer for HTTP status, cancellation
  or retry checks when those behaviors are part of the integration under test.
  Keep unit tests independent of live external services.
- Add a handwritten `ProviderSpyProtocol` wrapper when useful: increment,
  validate queued failure, then forward. Use Android's `failingMethods` member,
  `PlannedFailure` and `allMethods`; do not copy Swift spellings/signatures.
  Keep mutable spies isolated to one test.
- Match host testing conventions. The example uses JUnit, kotlin.test and
  coroutines `runTest`, with Given/When/Then and expected/actual comparisons.
  Compile consuming targets and run affected tests and Android lint. Report
  actual results; fixture success alone does not verify a live API or auth flow.

## Deliver in context

Implement in the existing checkout when one is supplied. For standalone output,
provide complete usable files and a ZIP when requested. Do not impose ZIP output
on in-place implementation or turn explanation requests into generated projects.

Use fictional User/Item examples and `example.com`. Changing the SDK's public API
is a separate task unless requested. Keep links/resources inside this skill so
the guide and example remain usable after installation in a consumer app.
