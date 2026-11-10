import iOSCleanNetworkTesting
import UserDomain

// One instance per test. This mutable spy is not intended for concurrent callers.
final class UserProviderSpy: UserProviderProtocol, ProviderSpyProtocol {
    enum MethodKey: Hashable, CaseIterable {
        case getUser
        case createUser
    }

    var invocationsCount: [MethodKey: Int] = [:]
    var failingMethos: [(method: MethodKey, error: any Error)] = []

    private let wrapped: any UserProviderProtocol

    init(wrapping wrapped: any UserProviderProtocol) {
        self.wrapped = wrapped
    }

    func getUser(id: Int) async throws -> User {
        increment(.getUser)
        try validateFailingMethods(method: .getUser)
        return try await wrapped.getUser(id: id)
    }

    func createUser(_ user: NewUser) async throws -> User {
        increment(.createUser)
        try validateFailingMethods(method: .createUser)
        return try await wrapped.createUser(user)
    }
}
