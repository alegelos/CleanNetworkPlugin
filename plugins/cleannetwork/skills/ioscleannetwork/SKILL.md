---
name: ioscleannetwork
description: Create or update Swift endpoint integrations using iOSCleanNetwork, including domain contracts, Setup and Provider types, request DTOs, response mapping, JSON fixtures and tests. Use when an app or SDK consumes iOSCleanNetwork or the user asks to generate an integration with it; not for unrelated networking libraries or general SDK maintenance.
metadata:
  api-baseline: "1.0.4"
---

# iOSCleanNetwork integration

Implement the consumer's feature using the installed SDK's actual contracts.
Keep the project's established module layout and honor the requested scope.
The SDK supplies transport and testing building blocks; feature-specific Setup,
Provider, Domain types and spies belong to the consumer.

## Establish the integration

1. Check the consumer's resolved SDK version and existing providers. This skill
   describes the API available in 1.0.4. Compare newer or older APIs with the
   installed source before using a signature that may differ. If the SDK is
   already integrated, reuse that dependency.
2. Read [the integration guide](references/integration.md). Inspect the relevant
   files in the [User example](assets/UserExample/) for code, resources and
   tests. Read only the parts needed by the feature; the example is a small
   reference, not an instruction to add a second networking architecture.
3. Establish the HTTP method/path, base URL, authentication and request/response
   contract from the user's API documentation. Ask for missing information that
   would change behavior. Do not invent endpoints, credentials, required fields
   or a token-refresh flow from a successful JSON sample.

## Apply the pattern

- Domain protocols take and return Domain values. Keep transport request DTOs,
  Decodable responses and their mappings in Data. Do not make Domain depend on
  Data or on the networking SDK merely to accept a request DTO.
- Use `*Setup: ApiSetupProtocol` for endpoint configuration and `*Provider` for
  the feature's implementation. Use request `*DTO`, response `*Response` and a
  response `.domain` mapper in new code. Preserve deliberate existing project
  conventions instead of renaming unrelated code.
- Group related endpoints in one Setup enum/provider when it fits the feature.
  A bodyless GET does not require a request DTO. Generate only relevant files.
- Inject `any NetworkSessionProtocol`. Call `session.data(for: setup)` so the
  SDK's URLSession implementation validates HTTP responses and the same provider
  can use the fixture session. Avoid bypassing it with `URLSession.shared`
  inside a provider method.
- Propagate encoding/decoding/mapping errors. `body` is nonthrowing in the SDK;
  the User example encodes with `try` before constructing a Setup with `Data`.
  Do not silently turn a failed encoding into an empty body with `try?`.
- Use the SDK's refresh helper only when the API and app supply an appropriate
  `ApisGatewayProtocol`. Keep credentials and token acquisition in the app's
  existing authentication design.
- `ApiProvider` is an optional configuration protocol, not a concrete client or
  a required superclass. Check unsupported methods or other SDK limitations in
  the guide rather than inventing members.

## Verify the integration

- Test the production provider with `MockedURLSession`, response JSON fixtures
  and a test-only `URLSessionSetupProtocol` conformance. Supply the bundle that
  actually contains the fixtures; SwiftPM test resources use `.module`. For a
  conformance added from a separate test module with `@testable import`, declare
  `jsonFileName` and `jsonBundle` as `public`, as the example does.
- Test request construction separately. The fixture session does not evaluate
  `setup.request` or simulate an HTTP status code; a green mapping test alone
  does not verify the outgoing URL, headers or payload.
- Add a handwritten `ProviderSpyProtocol` wrapper only when call observation or
  injected failures are useful. It increments, validates queued failures, then
  forwards. Keep mutable test doubles isolated to their test; do not add
  unchecked concurrency promises to silence a compiler error.
- Domain stubs can test Presenter/ViewModel behavior independently. A service
  spy aggregator is optional when several providers make tests noisy.
- Run the host's appropriate build and affected tests. Report actual results
  and any unverified parts. Never claim that reading a JSON fixture proves
  real network behavior, authentication or server-side effects.

## Deliver in the requested context

In an existing checkout, implement the requested files there and keep the
integration consistent with that project. For a standalone deliverable, provide
complete usable files and a ZIP when requested. Do not impose ZIP delivery on
in-place work or turn a request for explanation into file generation.

Use fictional data and `example.com` for examples. Keep the workflow scoped to
the integration; changing the SDK's public API is a separate task unless the
user has requested it.
