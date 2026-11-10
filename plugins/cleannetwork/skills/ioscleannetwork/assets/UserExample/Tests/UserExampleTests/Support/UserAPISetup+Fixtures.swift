import Foundation
import iOSCleanNetworkTesting
@testable import UserData

// Keep fixture routing in the test target; production endpoints do not depend on testing tools.
extension UserAPISetup: URLSessionSetupProtocol {
    public var jsonFileName: String {
        switch self {
        case .getUser: "GetUser"
        case .createUser: "CreateUser"
        }
    }

    public var jsonBundle: Bundle { .module }
}
