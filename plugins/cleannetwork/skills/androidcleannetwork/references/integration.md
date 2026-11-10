# Integrating AndroidCleanNetwork

This is the canonical reference for the [AndroidCleanNetwork skill](../SKILL.md).
The [User example](../assets/UserExample/) contains complete Kotlin code, Gradle
configuration, resources and tests. Adapt it to the consumer's existing layout.

## Establish the contract and dependency

Inspect the host's resolved SDK, existing providers, codec, dependency injection
and test conventions first. This guide targets the source declaring version
**1.0.1** in this checkout. That is not a promise of a published Maven release or
of identical behavior in another commit with the same local version. Check actual
installed interfaces and release information before generating integrations.

The runtime coordinate is `com.alegelos:android-clean-network:1.0.1`; test helpers
are `com.alegelos:android-clean-network-testing:1.0.1`. The checkout uses Gradle
8.10.2, Kotlin 2.1.0, AGP 8.7.3 and JDK 17, with compileSdk 35 and minSdk 23. The
example uses a Gradle composite build against `ANDROID_CLEAN_NETWORK_PATH`, an
explicit path to an SDK checkout. Its [settings](../assets/UserExample/settings.gradle.kts)
substitute both coordinates with local modules. Do not invent a Maven repository
or duplicate a dependency already integrated in the host.

Confirm method, base URL, path, query, body, successful/error response shapes and
authentication from endpoint documentation. JSON examples do not establish
required/optional fields, nullability or the non-null type of a null-only field.
Ask for missing facts that change behavior while progressing on independent
parts. Do not infer pagination, token storage or an OAuth flow from a success JSON.

## Keep Domain independent

| Layer | Example | Purpose |
| --- | --- | --- |
| Domain | `User(id: Int, name: String)`, `NewUser(name: String)` | Feature output and input |
| Domain | `UserProviderProtocol` | Feature operations |
| Data | `UserApiSetup` | Request construction |
| Data | `CreateUserDTO` | Encodable API request |
| Data | `UserResponse` and `.domain` | Decodable response and mapping |
| Data | `UserApiProvider` | Convert input, execute, decode and map |
| Tests | Resolver, JSON, provider/request tests and optional spy | Verify actual integration behavior |

The example's [user-domain](../assets/UserExample/user-domain/) is pure Kotlin/JVM
and has no SDK or codec dependency. [user-data](../assets/UserExample/user-data/)
is an Android library depending on Domain and the SDK. Separate modules enforce
the boundary here; use existing folders/modules in an established app.

```kotlin
interface UserProviderProtocol {
    suspend fun getUser(id: Int): User
    suspend fun createUser(user: NewUser): User
}
```

Both sides of the Domain interface use Domain values. The provider constructs
`CreateUserDTO` from `NewUser`; it never asks Domain callers to pass a Data DTO.
Keep responses and `.domain` mappings in Data. Related GET/POST endpoints share
one sealed `UserApiSetup` and one provider. A bodyless GET does not need a DTO.

`*Setup`, `*Provider`, `*Protocol`, `*DTO`, `*Response` and `.domain` are integration
conventions. Preserve deliberate equivalent names in existing code. Expose only
the public feature surface; the example's Setup, DTO and response are internal.

## Build a request

`ApiSetupProtocol` requires all six properties:

| Property | Type |
| --- | --- |
| `request` | `NetworkRequest` |
| `path` | `String` |
| `method` | `HttpMethod` |
| `headers` | `Map<String, String>` |
| `body` | `ByteArray?` |
| `queryParameters` | `List<QueryParameter>` |

Unlike the Swift counterpart, Android supplies `ApiRequestBuilder.build(...)`.
Pass the setup properties into it explicitly; merely declaring a query property
does not attach it to a request. `NetworkRequest` contains `url: java.net.URL`,
`method`, `headers` and optional encoded `body`.

- `HttpMethod` has exactly `GET`, `POST`, `PUT`, `PATCH`. Do not generate DELETE
  or HEAD enum members that the SDK does not provide.
- The builder accepts HTTP(S) base URLs and combines the base path prefix with
  the endpoint path, accepting a leading slash on the endpoint. `path` is an
  **unescaped hierarchical path**: `/` separates segments, not identifier data.
  Validate dynamic identifiers according to the endpoint contract. Do not pass
  a pre-percent-encoded path and expect it to be treated as raw encoded bytes.
- Existing base path escapes are preserved. New path text is URI-encoded; query
  names/values use UTF-8 form encoding (a space becomes `+`). Existing base query
  items are retained and new ones appended. Repeated names and null-valued
  flag parameters are supported. A base fragment is retained in the constructed
  URL; fragments are not HTTP request-target data.
- Build query values with `QueryParameter(name, value)`, not string concatenation.
  Decide whether inherited base query items are appropriate for the API. A base
  URL with credentials or unexpected query state should not come from arbitrary
  user input.
- Use `null` for a bodyless GET. OkHttp requires a non-null body for POST/PUT/PATCH;
  for an endpoint with an intentionally empty body, pass `byteArrayOf()` according
  to its contract. A GET with a body and a POST with `null` are rejected by OkHttp
  request construction with `IllegalArgumentException`, not `ApiErrors.InvalidBody`.
- Encode JSON before constructing the setup. Set `Content-Type: application/json`
  for a JSON body and `Accept` as appropriate. Authentication headers belong only
  on endpoints that require them. Do not suppress encoding errors with fallback
  empty bytes or construct JSON with string interpolation.

The example uses `GetUser(baseUrl, id)` and `CreateUser(baseUrl, body)`. The provider
passes encoded bytes to the POST setup. Invalid URL construction becomes
`ApiErrors.InvalidUrl`; SDK methods do not enforce your API's parameter/business
rules, so validate those in the relevant consumer layer.

## Execute, decode and map

`NetworkSessionProtocol` requires **both** suspend functions:

```kotlin
suspend fun dataFor(apiRequestSetup: ApiSetupProtocol): NetworkResponse

suspend fun dataWithUnauthorizedRefreshRetry(
    apiAccessProvider: ApisGatewayProtocol,
    buildEndpoint: (accessToken: String) -> ApiSetupProtocol,
): NetworkResponse
```

A custom session must implement both; the interface supplies no default transport
or retry. Inject it into the provider, defaulting to `DefaultNetworkSession` when
appropriate. Do not create a new client inside every provider method.
`DefaultNetworkSession` shares one OkHttp client and connection pool. Inject an
`OkHttpNetworkSession(configuredClient)` for app-specific interceptors or timeouts.

`ApiProvider` is an optional interface exposing `baseUrl: URL` and
`session: NetworkSessionProtocol`. It provides no constructor, decoding or concrete
feature implementation. Implementing the Domain interface is sufficient.

`NetworkResponse` contains raw `data: ByteArray`, `statusCode: Int`,
`headers: Map<String, List<String>>` and an optional `url: URL`. The SDK provides
no JSON serializer. Reuse the app's configured codec. The sample uses the Kotlin
serialization plugin and JSON runtime in Data; copying `@Serializable` classes
without configuring that plugin/runtime is insufficient.

The create flow is Domain input → request DTO → encoded bytes → Setup → injected
session → decoded response → `.domain`. GET uses the same decode/map path without
a request DTO. Configure unknown fields, naming, dates, nullability and defaults
according to the API, and test those decisions. Do not use a regular expression
as a JSON decoder or swallow malformed responses into empty/default Domain values.

For a list envelope, decode its documented container and map every element, for
example `response.items.map { it.domain }`. Nullable and absent are distinct API
decisions; kotlinx.serialization defaults affect whether a missing property is
accepted. A nullable property without a default can still be required in JSON.
Mapping may throw to enforce Domain invariants; propagate or deliberately
translate those errors. Handle 204/empty responses according to each endpoint's
contract rather than decoding every successful response as the same object.

## Real transport, errors and cancellation

`OkHttpNetworkSession` constructs the request, performs I/O off the caller's main
thread, reads the body and closes the OkHttp response. Coroutine cancellation
cancels the underlying call, including a call waiting for headers or reading a
body. Preserve cancellation when wrapping providers; do not turn it into a normal
error result or automatic retry.

The built-in HTTP validation maps:

| Status | Result |
| --- | --- |
| 200–299 | Return `NetworkResponse` |
| 400 | `ApiErrors.InvalidBody` |
| 401 | `ApiErrors.Unauthorized` |
| 403 | `ApiErrors.Forbidden` |
| 404 | `ApiErrors.NotFound` |
| 500–599 | `ApiErrors.ServerError` |
| Other | `ApiErrors.Undefined` |

Socket timeouts and OkHttp's total call timeout become `ApiErrors.TimeOut`.
Other `IOException`s become `ApiErrors.NetworkFailure` retaining the cause.
Cancellation propagates as cancellation; request-construction and codec errors
are not universally converted into `ApiErrors`. The similarly named SDK error
cases do not imply that the session automatically detects every such condition.
Custom sessions define their own behavior; interface conformance alone does not
install this HTTP validation. Android's I/O wrapping differs from the Swift SDK.

## Optional authentication and one retry

The app implements `ApisGatewayProtocol.apisAccessToken(policy)` and owns token
acquisition, storage, cache policy and concurrent refresh coordination. The SDK
implements none of those mechanisms.

`AccessTokenPolicy.Default` is `UseCache(minTtlSeconds = 180)` — three minutes.
`ForceRefresh` requests a new token. Honoring these requests is the gateway's job.
The built-in production and fixture retry helpers:

1. Obtain a token with the default policy, build the Setup from it and execute.
2. If that initial block throws `ApiErrors.Unauthorized`, obtain a token with
   `ForceRefresh`, rebuild the endpoint from the new token and execute once more.
3. Propagate all errors from the second attempt. There is no third attempt,
   general backoff or refresh deduplication.

The initial catch includes errors from token acquisition and setup construction,
not just an HTTP 401. Other errors and cancellation do not trigger this refresh.
Read the lambda's token parameter when building authorization headers so the
second request does not reuse a captured stale token. Prepare request DTO/body
outside the lambda when appropriate. Add no authentication scaffolding for an
unauthenticated endpoint merely to resemble another example.

## Fixtures and provider tests

Use the **production provider**, its real Setup, real codec and real `.domain`
mapping with `MockedNetworkSession`. Its constructor takes:

```kotlin
MockedNetworkSession(
    fixtureAnchor = UserApiProviderTest::class.java,
    fixtureFileNameFor = { setup ->
        when (setup) {
            is UserApiSetup.GetUser -> "fixtures/GetUser.json"
            is UserApiSetup.CreateUser -> "fixtures/CreateUser.json"
            else -> null
        }
    },
)
```

Keep the resolver in test code. Kotlin does **not** need a test-only Setup subtype
or an extra fixture interface on production Setup. The resource path is relative
to the classpath root, includes `.json`, and has no leading slash. Use a test class
as the anchor and place files under `src/test/resources/fixtures`. These are JVM
unit test resources; an app's Android `assets`/`res` and instrumentation resources
need their own integration rather than an assumed classpath lookup.

`MockedNetworkSession` resolves the filename, reads bytes, then evaluates
`apiRequestSetup.request.url` to construct a status-200 `NetworkResponse`. Missing
mapping throws `MockedNetworkSession.Errors.FixtureNotMapped`; missing classpath
resource throws `JsonReader.Errors.FileNameNotFound`. Directly calling
`JsonReader.localJson(null, anchor)` throws `NilFileName`. Stream-read errors
propagate. A request getter can also throw when the mock reads its URL.

The mock does not perform HTTP, assert headers/body/query, or turn an error-shaped
fixture into a 401/500. Its retry helper mirrors production control flow, but
resource loading does not create an HTTP unauthorized response. Gateway, resolver
or request-construction errors can still enter that helper's catch.

| Check | Suitable technique |
| --- | --- |
| Decode and map through the real provider | Fixture session + Domain assertions |
| URL, query, method, headers, payload | Inspect the real Setup's `request`; compare decoded JSON structure |
| Provider propagates codec, mapping and transport failures | Purpose-built injected session or focused mapper checks |
| HTTP statuses, rebuilt auth headers and retry counts | Real `OkHttpNetworkSession` + local MockWebServer |
| Cancellation and resource cleanup | Deterministically coordinate a real pending local call and cancellation |

The [example tests](../assets/UserExample/user-data/src/test/) use JUnit,
`kotlin.test` and coroutines `runTest`. Keep Given/When/Then clear and prefer
expected/actual comparisons. Assert structural JSON instead of object key order.
Test relevant missing/malformed fields, mapping, query and body edge cases.
For retry integrations, cover first success, unauthorized then success, repeated
unauthorized, other failures and refresh failure. Avoid live external services.

ViewModel tests may inject the real fixture-backed provider to check a feature
flow, or a Domain stub to isolate presentation behavior. Assert relevant loading,
success and failure transitions; do not claim a fixture test proves server behavior.

## Provider spies and optional aggregation

Concrete spies are handwritten in the consumer's test code. Implement the Domain
interface and `ProviderSpyProtocol<MethodKey>`, where MethodKey is an enum. Supply
`allMethods: Array<MethodKey>`, mutable `invocationsCount` and mutable
`failingMethods: MutableList<PlannedFailure<MethodKey>>`.

Each method increments its count, validates a queued failure, then forwards the
original arguments to the wrapped Domain provider. Failed calls count too.

- `enqueueFailures(items)` appends planned errors. Validation removes and throws
  the first entry matching the called method; ordering is FIFO per method.
- `assertExpectedInvocations(listOf(Method.Load to 1))` also checks zero calls for
  every unlisted case in `allMethods`. A mismatch throws `IllegalStateException`.
  Supply every enum case in `allMethods`; the helper cannot discover omitted ones.
- `resetInvocationsCount()` clears counts only, not queued failures.
- Helpers do not synchronize mutable state. Keep each spy local to one test or
  give it the isolation required by the host; do not share it across concurrent
  tests without coordination.

Use an aggregate spy only when several providers make higher-level tests clearer.
Preserve zero-call checks for omitted providers if the aggregate promises them.
The single-provider sample does not need an aggregator. Android's spelling is
`failingMethods`; do not copy the Swift SDK's legacy spelling or assertions.

## Verify a consuming project

Run the host's relevant build, unit tests and lint with its supported JDK/SDK.
Compile consuming modules to check visibility, resources, plugin configuration
and linkage. The installed example includes its own Gradle wrapper. From its
`assets/UserExample` directory:

```sh
ANDROID_CLEAN_NETWORK_PATH=/absolute/path/to/AndroidCleanNetwork \
  ./gradlew :user-domain:build :user-data:testDebugUnitTest \
  :user-data:lintDebug :user-data:assembleDebug --no-daemon
```

Set `JAVA_HOME` to JDK17 and `ANDROID_HOME` to the SDK when needed. Install SDK
platform35 using the host's normal toolchain setup. The environment path selects
the actual SDK being tested; the skill does not contain a second SDK copy.

These commands run JVM unit tests plus Android compilation and lint, not an
emulator/instrumentation suite. Run device-specific checks when the host feature
requires them. Report actual commands/results and remaining limits. Keep build
caches, machine-specific settings and production credentials out of deliverables.
