package com.example.user.data

import com.alegelos.androidcleannetwork.ApiErrors
import com.alegelos.androidcleannetwork.HttpMethod
import java.net.URL
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Test

class UserApiSetupTest {
    @Test
    fun getUserBuildsRequest() {
        val setup = UserApiSetup.GetUser(URL("https://api.example.com"), id = 1)

        val request = setup.request

        assertEquals("https://api.example.com/users/1", request.url.toExternalForm())
        assertEquals(HttpMethod.GET, request.method)
        assertEquals(mapOf("Accept" to "application/json"), request.headers)
        assertNull(request.body)
        assertEquals(emptyList(), setup.queryParameters)
    }

    @Test
    fun createUserUsesTheAlreadyEncodedBody() {
        val body = """{"name":"Jordan"}""".encodeToByteArray()
        val setup = UserApiSetup.CreateUser(URL("https://api.example.com"), body = body)

        val request = setup.request

        assertEquals("https://api.example.com/users", request.url.toExternalForm())
        assertEquals(HttpMethod.POST, request.method)
        assertEquals(
            mapOf("Accept" to "application/json", "Content-Type" to "application/json"),
            request.headers,
        )
        assertContentEquals(body, request.body)
        assertEquals(
            buildJsonObject { put("name", "Jordan") },
            Json.parseToJsonElement(requireNotNull(request.body).decodeToString()),
        )
    }

    @Test
    fun bothOperationsPreserveTheBasePath() {
        listOf("https://api.example.com/v1", "https://api.example.com/v1/").forEach { baseUrl ->
            val get = UserApiSetup.GetUser(URL(baseUrl), id = 42).request
            val create = UserApiSetup.CreateUser(URL(baseUrl), body = byteArrayOf()).request

            assertEquals("https://api.example.com/v1/users/42", get.url.toExternalForm())
            assertEquals("https://api.example.com/v1/users", create.url.toExternalForm())
        }
    }

    @Test
    fun rejectsANonHttpBaseUrl() {
        val setup = UserApiSetup.GetUser(URL("file:///users"), id = 1)

        assertSame(ApiErrors.InvalidUrl, assertFailsWith<ApiErrors> { setup.request })
    }
}
