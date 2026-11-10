import Foundation
import iOSCleanNetwork
import iOSCleanNetworkTesting
import Testing
import UserDomain
@testable import UserData

struct UserAPIProviderTests {
    @Test
    func getUserMapsFixtureToDomain() async throws {
        // Given
        let baseURL = try #require(URL(string: "https://api.example.com"))
        let provider = UserAPIProvider(baseURL: baseURL, session: MockedURLSession())
        let expected = User(id: 1, name: "Taylor")

        // When
        let actual = try await provider.getUser(id: 1)

        // Then
        #expect(actual == expected)
    }

    @Test
    func createUserMapsFixtureToDomain() async throws {
        // Given
        let baseURL = try #require(URL(string: "https://api.example.com"))
        let provider = UserAPIProvider(baseURL: baseURL, session: MockedURLSession())
        let expected = User(id: 2, name: "Jordan")

        // When
        let actual = try await provider.createUser(NewUser(name: "Jordan"))

        // Then
        #expect(actual == expected)
    }

    @Test
    func createUserEncodesDomainInputBeforeSending() async throws {
        // Given
        let baseURL = try #require(URL(string: "https://api.example.com"))
        let input = NewUser(name: "Avery \"AJ\" García")
        let response = try JSONReader.localJSON("CreateUser", in: .module)
        let session = StubNetworkSession(result: .success(response)) { request in
            #expect(request.url?.absoluteString == "https://api.example.com/users")
            #expect(request.httpMethod == "POST")
            let payload = try JSONDecoder().decode([String: String].self, from: #require(request.httpBody))
            #expect(payload == ["name": input.name])
        }
        let provider = UserAPIProvider(baseURL: baseURL, session: session)

        // When
        let user = try await provider.createUser(input)

        // Then
        // The server response, rather than the submitted input, defines the returned domain value.
        #expect(user == User(id: 2, name: "Jordan"))
    }

    @Test
    func malformedResponsePropagatesDecodingError() async throws {
        let baseURL = try #require(URL(string: "https://api.example.com"))
        let invalidResponse = Data(#"{"id":"one","name":"Taylor"}"#.utf8)
        let session = StubNetworkSession(result: .success(invalidResponse))
        let provider = UserAPIProvider(baseURL: baseURL, session: session)

        await #expect(throws: DecodingError.self) {
            try await provider.getUser(id: 1)
        }
    }

    @Test
    func transportErrorsPropagateFromBothOperations() async throws {
        let baseURL = try #require(URL(string: "https://api.example.com"))
        let session = StubNetworkSession(result: .failure(StubNetworkSession.Failure.unavailable))
        let provider = UserAPIProvider(baseURL: baseURL, session: session)

        await #expect(throws: StubNetworkSession.Failure.unavailable) {
            try await provider.getUser(id: 1)
        }
        await #expect(throws: StubNetworkSession.Failure.unavailable) {
            try await provider.createUser(NewUser(name: "Jordan"))
        }
    }

    @Test
    func missingFixtureThrows() {
        #expect {
            try JSONReader.localJSON("MissingUser", in: .module)
        } throws: { error in
            if case JSONReader.Errors.fileNameNotFound = error { true } else { false }
        }
    }

    @Test
    func mockedSessionRejectsSetupWithoutFixtureConformance() async throws {
        let baseURL = try #require(URL(string: "https://api.example.com"))
        let request = try UserAPISetup.getUser(baseURL: baseURL, id: 1).request

        await #expect {
            try await MockedURLSession().data(for: RequestOnlySetup(request: request))
        } throws: { error in
            if case MockedURLSession.Errors.invalidMockedRequestSetup = error { true } else { false }
        }
    }
}

// This intentionally lacks URLSessionSetupProtocol, unlike the test-only UserAPISetup extension.
private struct RequestOnlySetup: ApiSetupProtocol {
    let request: URLRequest
    var path: String { request.url?.path ?? "" }
    var method: HttpMethod { .get }
    var headers: [String: String] { request.allHTTPHeaderFields ?? [:] }
    var body: Data? { request.httpBody }
    var queryItems: [URLQueryItem] { [] }
}
