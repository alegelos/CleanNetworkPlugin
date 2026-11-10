public protocol UserProviderProtocol {
    func getUser(id: Int) async throws -> User
    func createUser(_ user: NewUser) async throws -> User
}
