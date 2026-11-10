import Foundation
import iOSCleanNetwork

enum UserAPISetup: ApiSetupProtocol {
    case getUser(baseURL: URL, id: Int)
    case createUser(baseURL: URL, body: Data)

    private var baseURL: URL {
        switch self {
        case .getUser(let baseURL, _), .createUser(let baseURL, _):
            baseURL
        }
    }

    var path: String {
        switch self {
        case .getUser(_, let id): "users/\(id)"
        case .createUser: "users"
        }
    }

    var method: HttpMethod {
        switch self {
        case .getUser: .get
        case .createUser: .post
        }
    }

    var headers: [String: String] {
        switch self {
        case .getUser:
            ["Accept": "application/json"]
        case .createUser:
            ["Accept": "application/json", "Content-Type": "application/json"]
        }
    }

    var body: Data? {
        switch self {
        case .getUser: nil
        case .createUser(_, let body): body
        }
    }

    var queryItems: [URLQueryItem] { [] }

    var request: URLRequest {
        get throws {
            let endpointURL = baseURL.appendingPathComponent(path)
            guard var components = URLComponents(url: endpointURL, resolvingAgainstBaseURL: false),
                  let scheme = components.scheme?.lowercased(),
                  ["https", "http"].contains(scheme),
                  components.host?.isEmpty == false else {
                throw ApiErrors.invalidUrl
            }

            components.queryItems = queryItems.isEmpty ? nil : queryItems
            guard let url = components.url else {
                throw ApiErrors.invalidUrl
            }

            var request = URLRequest(url: url)
            request.httpMethod = method.rawValue
            request.allHTTPHeaderFields = headers
            request.httpBody = body
            return request
        }
    }
}
