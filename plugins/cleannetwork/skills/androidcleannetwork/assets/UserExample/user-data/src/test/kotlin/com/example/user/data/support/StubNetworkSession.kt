package com.example.user.data.support

import com.alegelos.androidcleannetwork.ApiSetupProtocol
import com.alegelos.androidcleannetwork.ApisGatewayProtocol
import com.alegelos.androidcleannetwork.NetworkRequest
import com.alegelos.androidcleannetwork.NetworkResponse
import com.alegelos.androidcleannetwork.NetworkSessionProtocol

internal class StubNetworkSession(
    private val result: Result<ByteArray>,
    private val inspectRequest: (NetworkRequest) -> Unit = {},
) : NetworkSessionProtocol {
    override suspend fun dataFor(apiRequestSetup: ApiSetupProtocol): NetworkResponse {
        val request = apiRequestSetup.request
        inspectRequest(request)
        return NetworkResponse(
            data = result.getOrThrow(),
            statusCode = 200,
            url = request.url,
        )
    }

    override suspend fun dataWithUnauthorizedRefreshRetry(
        apiAccessProvider: ApisGatewayProtocol,
        buildEndpoint: (accessToken: String) -> ApiSetupProtocol,
    ): NetworkResponse = error("Retry is not used by this example.")
}
