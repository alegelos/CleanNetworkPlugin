import Foundation
import iOSCleanNetworkTesting
import Testing
import UserData
import UserDomain

struct UserProviderSpyTests {
    @Test
    func forwardsDomainArgumentsAndCountsCalls() async throws {
        let baseURL = try #require(URL(string: "https://api.example.com"))
        let response = try JSONReader.localJSON("GetUser", in: .module)
        let session = StubNetworkSession(result: .success(response)) { request in
            switch request.httpMethod {
            case "GET":
                #expect(request.url?.path == "/users/42")
            case "POST":
                let payload = try JSONDecoder().decode([String: String].self, from: #require(request.httpBody))
                #expect(payload == ["name": "Avery"])
            default:
                Issue.record("Unexpected request method: \(request.httpMethod ?? "nil")")
            }
        }
        let provider = UserAPIProvider(baseURL: baseURL, session: session)
        let spy = UserProviderSpy(wrapping: provider)

        let fetchedUser = try await spy.getUser(id: 42)
        let createdUser = try await spy.createUser(NewUser(name: "Avery"))

        #expect(fetchedUser == User(id: 1, name: "Taylor"))
        #expect(createdUser == User(id: 1, name: "Taylor"))
        spy.assertExpectedInvocations([(.getUser, 1), (.createUser, 1)])
    }

    @Test
    func countsFailuresAndConsumesFirstFailureMatchingMethod() async throws {
        let baseURL = try #require(URL(string: "https://api.example.com"))
        let response = try JSONReader.localJSON("GetUser", in: .module)
        let session = StubNetworkSession(result: .success(response)) { request in
            // Only the successful GET may reach the wrapped provider's transport.
            #expect(request.url?.path == "/users/1")
            #expect(request.httpMethod == "GET")
        }
        let provider = UserAPIProvider(baseURL: baseURL, session: session)
        let spy = UserProviderSpy(wrapping: provider)
        spy.failingMethods([
            (.createUser, StubNetworkSession.Failure.queuedCreate),
            (.getUser, StubNetworkSession.Failure.queuedGet)
        ])

        await #expect(throws: StubNetworkSession.Failure.queuedGet) {
            try await spy.getUser(id: 999)
        }
        // Unlisted createUser must still have zero calls, despite its earlier queued failure.
        spy.assertExpectedInvocations([(.getUser, 1)])
        #expect(spy.failingMethos.count == 1)

        let user = try await spy.getUser(id: 1)
        #expect(user == User(id: 1, name: "Taylor"))

        await #expect(throws: StubNetworkSession.Failure.queuedCreate) {
            try await spy.createUser(NewUser(name: "Jordan"))
        }
        spy.assertExpectedInvocations([(.getUser, 2), (.createUser, 1)])
        #expect(spy.failingMethos.isEmpty)
    }
}
