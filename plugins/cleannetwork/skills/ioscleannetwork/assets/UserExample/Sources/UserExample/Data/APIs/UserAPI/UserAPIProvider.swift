import Foundation
import iOSCleanNetwork
import UserDomain

public struct UserAPIProvider: ApiProvider, UserProviderProtocol {
    public let baseURL: URL
    public let session: any NetworkSessionProtocol

    public init(baseURL: URL, session: any NetworkSessionProtocol = URLSession.shared) {
        self.baseURL = baseURL
        self.session = session
    }

    public func getUser(id: Int) async throws -> User {
        let setup = UserAPISetup.getUser(baseURL: baseURL, id: id)
        let (data, _) = try await session.data(for: setup)
        return try JSONDecoder().decode(UserResponse.self, from: data).domain
    }

    public func createUser(_ user: NewUser) async throws -> User {
        let dto = CreateUserDTO(user)
        let body = try JSONEncoder().encode(dto)
        let setup = UserAPISetup.createUser(baseURL: baseURL, body: body)
        let (data, _) = try await session.data(for: setup)
        return try JSONDecoder().decode(UserResponse.self, from: data).domain
    }
}
