import Foundation
import iOSCleanNetwork

// Immutable state keeps this Sendable test transport safe without unchecked conformance.
final class StubNetworkSession: NetworkSessionProtocol {
    private let result: Result<Data, any Error>
    private let inspectRequest: @Sendable (URLRequest) throws -> Void

    init(
        result: Result<Data, any Error>,
        inspectRequest: @escaping @Sendable (URLRequest) throws -> Void = { _ in }
    ) {
        self.result = result
        self.inspectRequest = inspectRequest
    }

    func data(for apiRequestSetup: any ApiSetupProtocol) async throws -> (Data, URLResponse) {
        let request = try apiRequestSetup.request
        try inspectRequest(request)
        let data = try result.get()
        guard let url = request.url else {
            throw ApiErrors.invalidUrl
        }
        let response = URLResponse(
            url: url,
            mimeType: "application/json",
            expectedContentLength: data.count,
            textEncodingName: "utf-8"
        )
        return (data, response)
    }

    func dataWithUnauthorizedRefreshRetry(
        apiAccessProvider: any ApisGatewayProtocol,
        buildEndpoint: (String) -> any ApiSetupProtocol
    ) async throws -> (Data, URLResponse) {
        throw Failure.unsupportedRetry
    }

    enum Failure: Error, Equatable {
        case unavailable
        case queuedGet
        case queuedCreate
        case unsupportedRetry
    }
}
