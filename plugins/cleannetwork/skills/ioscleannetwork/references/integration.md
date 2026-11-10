# Integrating iOSCleanNetwork

This is the technical reference for the [iOSCleanNetwork skill](../SKILL.md). The [executable User example](../assets/UserExample/) contains the complete implementation and tests; use it as a pattern, adapting the existing application's structure and conventions.

## Establish the contract first

1. Inspect the host's dependency declaration, resolved package version, SDK interfaces and existing networking code. These instructions and the example use SDK **1.0.4** as their baseline; the example's dependency requirement starts at `1.0.4`. Follow the version actually installed and check compatibility before using another version's API. SDK 1.0.4 declares Swift tools 6.2 and iOS 15 as its minimum iOS deployment target.
2. Read the supplied endpoint documentation or schema and request/response examples. Confirm the base URL, paths, methods, parameters, payloads, response shapes and authentication needed by the requested feature. Do not invent fields, pagination, token storage or unsupported methods.
3. Reuse existing Domain contracts, dependency injection, targets and folders. Add only missing files. Ask for essential missing API information while progressing with independent work; do not replace a working architecture with the example's package layout.
4. Implement in the host project by default. Produce a standalone package or downloadable zip when requested; packaging is not a prerequisite for an integration in an existing checkout.

The runtime product is `iOSCleanNetwork`. Add `iOSCleanNetworkTesting` to the relevant test target for fixtures and spies. Do not duplicate an SDK dependency already present in the host. The [example manifest](../assets/UserExample/Package.swift) shows dependency declarations, target boundaries and resource processing.

## Keep Domain independent of transport

The example groups `GET /users/{id}` and `POST /users` behind one `UserAPISetup` enum and one `UserAPIProvider`. Its fictional base URL is `https://api.example.com`. Group related endpoints this way when it fits the host's conventions.

| Layer | Consumer-owned types | Responsibility |
| --- | --- | --- |
| Domain | `User`, `NewUser`, `UserProviderProtocol` | Feature-facing output, input and capabilities |
| Data | `CreateUserDTO` | Encode the request's transport shape |
| Data | `UserResponse` and its `.domain` mapper | Decode transport data and produce a Domain value |
| Data | `UserAPISetup` | Build endpoint requests |
| Data | `UserAPIProvider` | Convert inputs, call the injected session, decode and map outputs |
| Tests | Fixtures, setup extension, provider tests and optional spies | Verify the real integration and selected higher-level behavior |

The example's Domain contract is:

```swift
public protocol UserProviderProtocol {
    func getUser(id: Int) async throws -> User
    func createUser(_ user: NewUser) async throws -> User
}
```

`User` contains `id: Int` and `name: String`; `NewUser` contains `name: String`. Domain imports neither the SDK nor Data. Both inputs and outputs crossing this boundary use Domain types; `CreateUserDTO` and `UserResponse` stay in Data. The provider conforms to the Domain protocol, and presentation code depends on that protocol.

The `*Setup`, `*Provider`, `*DTO`, `*Response`, `*Protocol` suffixes and `.domain` property are integration conventions, not compiler requirements imposed by the SDK. Follow established equivalent host conventions. Swift conformance requires the exact public members of the SDK protocols. The example's DTO and setup are internal; expose only what consumers actually need.

If a new layout is needed, use `Domain/Models`, `Domain/Providers` and `Data/APIs/UserAPI` with setup, provider, DTO and response files. Put fixtures and test support in the test target. Separate modules are useful when the host already uses them; new modules are not mandatory.

## Construct requests with ApiSetupProtocol

Every conforming setup supplies all six properties; there is no SDK request builder or default implementation:

| Property | Required type and accessor | Meaning |
| --- | --- | --- |
| `request` | `URLRequest { get throws }` | Fully constructed request |
| `path` | `String { get }` | Endpoint path used by the setup's own builder |
| `method` | `HttpMethod { get }` | Supported HTTP method |
| `headers` | `[String: String] { get throws }` | Header values; access with `try` when needed |
| `body` | `Data? { get }` | Already encoded optional request body; this getter cannot throw |
| `queryItems` | `[URLQueryItem] { get }` | Parameters incorporated by the setup's own builder |

`HttpMethod` has exactly `.get`, `.post`, `.put` and `.patch`, with their uppercase raw values. SDK 1.0.4 has no `.delete` or `.head`. If the requested API needs another method, surface this compatibility requirement and agree on an explicit approach; do not generate nonexistent enum cases or silently substitute a method.

Use [UserAPISetup.swift](../assets/UserExample/Sources/UserExample/Data/APIs/UserAPI/UserAPISetup.swift) for the complete request builder. It defines `getUser(baseURL:id:)` and `createUser(baseURL:body:)`, with the POST case receiving encoded `Data`.

- Build URLs using `URL`/`URLComponents` and `URLQueryItem`. Define how the endpoint path combines with any base URL path prefix; do not interpolate unescaped user input into a URL string.
- Incorporate `queryItems` into the final URL. Merely declaring the property does nothing. Return `[]` when an endpoint has no query parameters. Preserve or replace base URL query items deliberately according to the API contract.
- Set `httpMethod = method.rawValue`, apply `try headers`, and set `httpBody = body`. Use `nil` for absent bodies. Add `Content-Type: application/json` for a JSON payload and authentication headers only when required.
- Validate request construction and propagate meaningful errors, such as `ApiErrors.invalidUrl`. Do not force-unwrap untrusted URLs or hide an encoding error with `try?`.
- Encode a DTO with `try JSONEncoder().encode(...)` before creating a setup, as the example provider does. A nonthrowing `body` getter must not turn a failed encoding operation into an unintended bodyless request.

For documented query parameters, create items such as `URLQueryItem(name: "name", value: requestedName)` instead of joining `"?name="` with raw input. Query DTOs may belong in Data when useful; do not add fields that the supplied endpoint contract does not define.

## Execute, decode and map in the provider

`NetworkSessionProtocol` is a class-bound, `Sendable` protocol. It requires **both** async throwing methods:

```swift
func data(for apiRequestSetup: ApiSetupProtocol) async throws -> (Data, URLResponse)

func dataWithUnauthorizedRefreshRetry(
    apiAccessProvider: ApisGatewayProtocol,
    buildEndpoint: (String) -> ApiSetupProtocol
) async throws -> (Data, URLResponse)
```

Inject `any NetworkSessionProtocol`; the example defaults to `URLSession.shared`. This allows the same concrete provider to use a real session, a fixture session or a purpose-built test session. A custom conforming class must implement both methods and meet `Sendable` requirements. Protect mutable shared state appropriately; do not add unchecked sendability simply to silence the compiler.

In [UserAPIProvider.swift](../assets/UserExample/Sources/UserExample/Data/APIs/UserAPI/UserAPIProvider.swift), `createUser(_:)` converts `NewUser` to `CreateUserDTO`, encodes it with `try`, builds the setup, calls `try await session.data(for: setup)`, decodes `UserResponse`, then returns `.domain`. `getUser(id:)` uses the same decode/map path without a request DTO.

`ApiProvider` is an optional SDK protocol with read-only `baseURL: URL` and `session: NetworkSessionProtocol` requirements. It supplies no concrete provider, factory, initializer, request construction, decoding or mapping. A provider can conform when useful, but conformance is not required to use an injected session or implement a Domain protocol.

Use `Decodable` response models with field types and optionality supported by the API evidence. Configure `JSONDecoder` explicitly when the API requires key, date or other decoding strategies; avoid assuming an SDK-wide decoder configuration. Keep a matching fixture and test for those choices. Do not swallow `DecodingError` or convert every failure into `ApiErrors.decodeError` without a deliberate host error policy.

Keep the mapper in Data as an extension of `UserResponse`. The example's mapping is direct. If a Domain invariant requires validation, give the `.domain` computed property a throwing getter; the provider must then use `try response.domain` and propagate or deliberately translate the mapping error. For collections, map every response to Domain, for example `try responses.map { try $0.domain }` when mapping throws. No transport response or request DTO should leak through the Domain protocol.

Handle empty or differently shaped successful responses according to the endpoint contract. A successful status does not imply that every endpoint returns a JSON object of the same type.

## What the real URLSession adapter validates

The SDK's `URLSession` conformance evaluates `try setup.request`, performs the request and validates the resulting HTTP response. It returns data for status codes `200..<300` and otherwise applies this mapping:

| Response | Error |
| --- | --- |
| Non-HTTP response | `ApiErrors.undefined` |
| 400 | `ApiErrors.invalidBody` |
| 401 | `ApiErrors.unauthorized` |
| 403 | `ApiErrors.forbidden` |
| 404 | `ApiErrors.notFound` |
| 500..<600 | `ApiErrors.serverError` |
| Other non-2xx status | `ApiErrors.undefined` |

Transport and request-construction errors propagate; the adapter does not convert all network errors to the similarly named `ApiErrors` cases. It does not decode response JSON. Other `NetworkSessionProtocol` implementations determine their own behavior: conformance alone does not install this HTTP validator.

## Optional authentication and one retry

Only add authentication scaffolding when the endpoint requires it. The application supplies an `ApisGatewayProtocol` class implementing `apisAccessToken(policy:) async throws -> String`. It owns fetching, refreshing, storing and caching the API access token, including concurrent refresh coordination. The SDK supplies neither a token service nor a cache implementation.

`AccessTokenPolicy.useCache(minTTL:)` expresses a requested minimum remaining lifetime; `.forceRefresh` requests a fresh token. `.default` is `.useCache(minTTL: 180)` — **three minutes**. The convenience call `apisAccessToken()` passes `.default`; honoring the policy is the gateway's responsibility.

The SDK's `dataWithUnauthorizedRefreshRetry(apiAccessProvider:buildEndpoint:)` implementations:

1. Obtain a token with the default policy and pass it into `buildEndpoint`.
2. Execute the resulting setup.
3. On `ApiErrors.unauthorized` from that initial attempt, obtain a token with `.forceRefresh`, rebuild the endpoint with the new token and execute once more.
4. Propagate errors from the second attempt; there is no third attempt or general retry/backoff mechanism.

The initial `do` block includes token acquisition, so an initial `ApiErrors.unauthorized` thrown by the gateway also enters this refresh path. Other errors propagate immediately. The closure is nonthrowing; perform throwing payload preparation before passing it. Read the closure's token argument when building headers so the retry cannot reuse a captured stale token. Do not add this helper to an unauthenticated endpoint merely to match an example.

## Fixture-based provider tests

Use Swift Testing (`import Testing`, `@Test`, `#expect`, `#require`) for new tests following this guide. Keep Given/When/Then clear, and prefer `expected`/`actual` for value comparisons. Match any established host testing conventions when adapting an existing suite.

Inject `MockedURLSession()` into the **real** `UserAPIProvider`. This preserves production DTO encoding, decoding and Domain mapping. A separate fake provider does not test that integration. Presentation or other higher-level tests may use a Domain stub when they are testing their own behavior.

The setup must also conform to `URLSessionSetupProtocol` with:

- `jsonFileName: String`: the fixture resource name **without** `.json`, chosen for each setup case.
- `jsonBundle: Bundle`: the bundle actually containing that fixture.

Keep the conformance in the test target when fixtures are only for tests. See [UserAPISetup+Fixtures.swift](../assets/UserExample/Tests/UserExampleTests/Support/UserAPISetup+Fixtures.swift). Use `@testable import UserData` for the example's internal setup. The test target processes `Resources` in [Package.swift](../assets/UserExample/Package.swift), allowing its extension to return `.module`. `Bundle.module` exists only in a SwiftPM target with resources; it is not an app-wide lookup.

When adding this conformance from a separate test module using `@testable import`, declare both `jsonFileName` and `jsonBundle` as `public`, following the example. The compiler requires these witnesses to satisfy the public protocol even though the setup is internal to the production module. Leaving them at their default access level prevents the test target from compiling; the setup itself does not need to become public.

For an Xcode test bundle, a marker class declared in that test target can locate its resources with `Bundle(for: FixtureBundleMarker.self)`. Ensure the JSON files have the correct target membership. `URLSessionSetupProtocol` defaults `jsonBundle` to `.main`; use that only when the fixtures really are in the main bundle. A file present in the source tree is not automatically a bundled test resource.

`MockedURLSession` casts the setup to `URLSessionSetupProtocol`, reads the selected JSON and returns its bytes with a placeholder `HTTPURLResponse()`. Missing conformance throws `MockedURLSession.Errors.invalidMockedRequestSetup`; missing resources throw `JSONReader.Errors.fileNameNotFound` (file-read errors also propagate).

It **does not** evaluate `setup.request`, validate URLs/headers/bodies, perform HTTP status validation, simulate a 401 response, or make a live HTTP call. A fixture containing an error-shaped JSON object does not become an HTTP error. Its retry method mirrors the SDK's retry structure, but fixture loading itself does not produce a status-derived unauthorized error; a gateway error can still trigger that path.

Separate the checks accordingly:

| Check | Technique | Example or boundary |
| --- | --- | --- |
| Decode and map fixture responses through the real provider | Inject `MockedURLSession`; assert Domain values | [UserAPIProviderTests.swift](../assets/UserExample/Tests/UserExampleTests/UserAPIProviderTests.swift) |
| Request construction | Evaluate `try setup.request`; assert URL/path, query items, method, headers and decoded body | [UserAPISetupTests.swift](../assets/UserExample/Tests/UserExampleTests/UserAPISetupTests.swift) |
| Decode, mapping and transport failures | Inject deterministic data/errors into the real provider; assert exact relevant behavior | Purpose-built session or focused mapper tests, according to the contract |
| Actual HTTP validation and unauthorized retry | Exercise the SDK's real `URLSession` adapter with a controlled local transport such as `URLProtocol` on supported platforms | Inspect statuses, token policies, attempt counts and rebuilt authorization headers; fixtures alone cannot prove these behaviors |

For request body assertions, decode the JSON or compare its structure instead of relying on JSON object key order. Cover required/optional fields, relevant malformed responses and request edge cases. For retry tests, check initial success, one unauthorized then success, repeated unauthorized propagation, non-unauthorized propagation and refresh failure when those paths are used. Keep real external network calls out of deterministic unit tests.

## Provider spies and optional aggregation

`ProviderSpyProtocol` is a Swift Testing helper for consumer-written spies. The SDK does not generate a concrete spy. See [UserProviderSpy.swift](../assets/UserExample/Tests/UserExampleTests/Support/UserProviderSpy.swift) and [UserProviderSpyTests.swift](../assets/UserExample/Tests/UserExampleTests/UserProviderSpyTests.swift).

A spy conforms to the Domain protocol and `ProviderSpyProtocol`, defines `MethodKey: Hashable & CaseIterable`, and stores:

```swift
var invocationsCount: [MethodKey: Int] = [:]
var failingMethos: [(method: MethodKey, error: Error)] = []
```

The public member really is spelled `failingMethos`; preserve that spelling. For each method, call `increment(...)`, then `try validateFailingMethods(method: ...)`, then forward arguments to the wrapped provider. Failed calls are counted too. Wrap a real provider with an injected session when testing Data behavior; a wrapped Domain stub is appropriate for tests of a Presenter or other consumer.

- `failingMethods(_:)` appends failures. Validation removes and throws the **first matching** queued failure for the method being called. Ordering is FIFO per method; an earlier entry for another method does not block it.
- `assertExpectedInvocations(_:)` checks supplied counts and asserts **zero** calls for every unlisted `MethodKey` case. It records Swift Testing issues and is nonthrowing; call it without `try`.
- `resetInvocationsCount()` clears counts only. It does not clear `failingMethos`.
- The helper does not synchronize mutable counters or queues. Keep each mutable spy isolated to its test's execution context; do not share it across parallel tests without appropriate isolation.

When a higher-level service coordinates several providers, a consumer-owned aggregator may hold their spies and delegate reset, failure injection and invocation assertions. Preserve zero-call checks for omitted providers if the aggregate API promises them. Do not create an aggregator for the single-provider User example or add one where it makes tests harder to follow.

## Verify the host integration

Run the host project's required build, type/static checks and affected tests using its supported toolchain. Include the real provider path, request construction, resource discovery, decoding/mapping and relevant failure paths. Build the consuming targets so target membership, access control and package-product linkage are checked as well.

For host tests on macOS 14+ with Swift 6.2+, run the following from this skill's `assets/UserExample` directory:

```sh
swift test --triple "$(uname -m)-apple-macosx14.0"
```

The explicit host target provides the macOS availability needed by the SDK and testing toolchain. This checks shared code on the host; it is not an iOS simulator test or a platform support guarantee. The example resolves the public dependency by default. To verify a local SDK checkout, prefix the command with `IOS_CLEAN_NETWORK_PATH=/absolute/path/to/iOSCleanNetwork`. Choose a full Xcode toolchain per command with `DEVELOPER_DIR` if needed. For iOS validation, open the example's `Package.swift` in Xcode and test its `UserExample` scheme on an available simulator. No test requires a live endpoint.

Report changed files, commands actually executed, results and any behavior left unvalidated. A fixture test passing does not establish that a live endpoint, HTTP status policy or authentication refresh works.
