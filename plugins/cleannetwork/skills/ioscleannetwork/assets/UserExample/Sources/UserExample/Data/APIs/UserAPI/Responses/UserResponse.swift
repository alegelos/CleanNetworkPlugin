import UserDomain

struct UserResponse: Decodable {
    let id: Int
    let name: String
}

extension UserResponse {
    var domain: User {
        User(id: id, name: name)
    }
}
