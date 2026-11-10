package com.example.user.data

import com.alegelos.androidcleannetwork.ApiRequestBuilder
import com.alegelos.androidcleannetwork.ApiSetupProtocol
import com.alegelos.androidcleannetwork.HttpMethod
import com.alegelos.androidcleannetwork.NetworkRequest
import com.alegelos.androidcleannetwork.QueryParameter
import java.net.URL

internal sealed class UserApiSetup(
    private val baseUrl: URL,
    final override val path: String,
    final override val method: HttpMethod,
    final override val headers: Map<String, String>,
    final override val body: ByteArray? = null,
) : ApiSetupProtocol {
    class GetUser(baseUrl: URL, id: Int) : UserApiSetup(
        baseUrl = baseUrl,
        path = "users/$id",
        method = HttpMethod.GET,
        headers = mapOf("Accept" to "application/json"),
    )

    class CreateUser(baseUrl: URL, body: ByteArray) : UserApiSetup(
        baseUrl = baseUrl,
        path = "users",
        method = HttpMethod.POST,
        headers = mapOf(
            "Accept" to "application/json",
            "Content-Type" to "application/json",
        ),
        body = body,
    )

    final override val queryParameters: List<QueryParameter> = emptyList()

    final override val request: NetworkRequest
        get() = ApiRequestBuilder.build(baseUrl, path, method, headers, body, queryParameters)
}
