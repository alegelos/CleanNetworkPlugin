package com.example.user.data

import com.alegelos.androidcleannetwork.ApiErrors
import com.alegelos.androidcleannetwork.HttpMethod
import com.alegelos.androidcleannetwork.NetworkRequest
import com.alegelos.androidcleannetwork.testing.JsonReader
import com.alegelos.androidcleannetwork.testing.MockedNetworkSession
import com.example.user.data.support.StubNetworkSession
import com.example.user.data.support.UserApiFixtures
import com.example.user.domain.NewUser
import com.example.user.domain.User
import java.io.IOException
import java.net.URL
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Test

class UserApiProviderTest {
    private val baseUrl = URL("https://api.example.com")

    @Test
    fun getUserMapsFixtureToDomain() = runTest {
        val provider = UserApiProvider(baseUrl, session = UserApiFixtures.session())

        val user = provider.getUser(id = 1)

        assertEquals(User(id = 1, name = "Taylor"), user)
    }

    @Test
    fun createUserMapsFixtureToDomain() = runTest {
        val provider = UserApiProvider(baseUrl, session = UserApiFixtures.session())

        val user = provider.createUser(NewUser(name = "Jordan"))

        assertEquals(User(id = 2, name = "Jordan"), user)
    }

    @Test
    fun createUserEncodesDomainInputAndReturnsTheServerValue() = runTest {
        val input = NewUser(name = "Avery \"AJ\" García\n")
        val requests = mutableListOf<NetworkRequest>()
        val session = StubNetworkSession(
            result = Result.success(JsonReader.localJson("fixtures/CreateUser.json", UserApiProviderTest::class.java)),
            inspectRequest = { requests += it },
        )
        val provider = UserApiProvider(baseUrl, session)

        val user = provider.createUser(input)

        val request = requests.single()
        assertEquals("https://api.example.com/users", request.url.toExternalForm())
        assertEquals(HttpMethod.POST, request.method)
        assertEquals("application/json", request.headers["Accept"])
        assertEquals("application/json", request.headers["Content-Type"])
        assertEquals(
            buildJsonObject { put("name", input.name) },
            Json.parseToJsonElement(requireNotNull(request.body).decodeToString()),
        )
        // The response, rather than the submitted input, defines the returned domain value.
        assertEquals(User(id = 2, name = "Jordan"), user)
    }

    @Test
    fun malformedResponsesPropagateSerializationErrors() = runTest {
        listOf("""{"id":1,"name":""", """{"id":"one","name":"Taylor"}""").forEach { response ->
            val session = StubNetworkSession(Result.success(response.encodeToByteArray()))
            val provider = UserApiProvider(baseUrl, session)

            assertFailsWith<SerializationException> { provider.getUser(id = 1) }
            assertFailsWith<SerializationException> { provider.createUser(NewUser(name = "Jordan")) }
        }
    }

    @Test
    fun missingRequiredFieldsAreRejected() = runTest {
        listOf("{}", """{"id":1}""", """{"name":"Taylor"}""").forEach { response ->
            val session = StubNetworkSession(Result.success(response.encodeToByteArray()))
            val provider = UserApiProvider(baseUrl, session)

            assertFailsWith<SerializationException> { provider.getUser(id = 1) }
            assertFailsWith<SerializationException> { provider.createUser(NewUser(name = "Jordan")) }
        }
    }

    @Test
    fun additionalResponseFieldsAreIgnored() = runTest {
        val response = """{"id":1,"name":"Taylor","extra":"server field"}""".encodeToByteArray()
        val provider = UserApiProvider(baseUrl, StubNetworkSession(Result.success(response)))

        val user = provider.getUser(id = 1)

        assertEquals(User(id = 1, name = "Taylor"), user)
    }

    @Test
    fun transportErrorsPropagateFromBothOperations() = runTest {
        val failure = ApiErrors.NetworkFailure(IOException("Test transport unavailable"))
        val provider = UserApiProvider(baseUrl, StubNetworkSession(Result.failure(failure)))

        assertSame(failure, assertFailsWith<ApiErrors.NetworkFailure> { provider.getUser(id = 1) })
        assertSame(
            failure,
            assertFailsWith<ApiErrors.NetworkFailure> { provider.createUser(NewUser(name = "Jordan")) },
        )
    }

    @Test
    fun missingFixtureFailsClearly() = runTest {
        val session = MockedNetworkSession(UserApiProviderTest::class.java) { "fixtures/MissingUser.json" }
        val provider = UserApiProvider(baseUrl, session)

        assertFailsWith<JsonReader.Errors.FileNameNotFound> { provider.getUser(id = 1) }
    }

    @Test
    fun unmappedSetupFailsClearly() = runTest {
        val session = MockedNetworkSession(UserApiProviderTest::class.java) { null }
        val provider = UserApiProvider(baseUrl, session)

        assertFailsWith<MockedNetworkSession.Errors.FixtureNotMapped> { provider.getUser(id = 1) }
    }
}
