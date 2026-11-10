import UserDomain

struct CreateUserDTO: Encodable {
    let name: String

    init(_ user: NewUser) {
        name = user.name
    }
}
