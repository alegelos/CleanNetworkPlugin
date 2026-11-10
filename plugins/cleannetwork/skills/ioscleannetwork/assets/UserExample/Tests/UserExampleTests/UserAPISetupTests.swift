import Foundation
import iOSCleanNetwork
import Testing
import UserDomain
@testable import UserData

struct UserAPISetupTests {
    @Test
    func getUserBuildsRequest() throws {
        // Given
        let baseURL = try #require(URL(string: "https://api.example.com"))

        // When
        let request = try UserAPISetup.getUser(baseURL: baseURL, id: 1).request

        // Then
        #expect(request.url?.absoluteString == "https://api.example.com/users/1")
        #expect(request.httpMethod == "GET")
        #expect(request.value(forHTTPHeaderField: "Accept") == "application/json")
        #expect(request.value(forHTTPHeaderField: "Content-Type") == nil)
        #expect(request.httpBody == nil)
    }

    @Test
    func requestPreservesBasePath() throws {
        let baseURL = try #require(URL(string: "https://api.example.com/v1"))
        let request = try UserAPISetup.getUser(baseURL: baseURL, id: 42).request

        #expect(request.url?.absoluteString == "https://api.example.com/v1/users/42")
    }

    @Test
    func createUserBuildsJSONRequest() throws {
        // Given
        let baseURL = try #require(URL(string: "https://api.example.com"))
        let body = try JSONEncoder().encode(CreateUserDTO(NewUser(name: "Jordan")))

        // When
        let request = try UserAPISetup.createUser(baseURL: baseURL, body: body).request

        // Then
        #expect(request.url?.absoluteString == "https://api.example.com/users")
        #expect(request.httpMethod == "POST")
        #expect(request.value(forHTTPHeaderField: "Accept") == "application/json")
        #expect(request.value(forHTTPHeaderField: "Content-Type") == "application/json")
        let payload = try JSONDecoder().decode([String: String].self, from: #require(request.httpBody))
        #expect(payload == ["name": "Jordan"])
    }

    @Test(arguments: ["/relative", "file:///users"])
    func rejectsNonHTTPBaseURL(_ value: String) throws {
        let baseURL = try #require(URL(string: value))

        #expect {
            try UserAPISetup.getUser(baseURL: baseURL, id: 1).request
        } throws: { error in
            if case ApiErrors.invalidUrl = error { true } else { false }
        }
    }
}
