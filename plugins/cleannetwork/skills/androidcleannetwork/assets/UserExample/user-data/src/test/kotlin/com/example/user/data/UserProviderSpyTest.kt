package com.example.user.data

import com.alegelos.androidcleannetwork.ApiSetupProtocol
import com.alegelos.androidcleannetwork.testing.MockedNetworkSession
import com.alegelos.androidcleannetwork.testing.PlannedFailure
import com.example.user.data.support.UserApiFixtures
import com.example.user.data.support.UserProviderSpy
import com.example.user.data.support.UserProviderSpy.MethodKey
import com.example.user.domain.NewUser
import com.example.user.domain.User
import java.io.IOException
import java.net.URL
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Test

class UserProviderSpyTest {
    private val baseUrl = URL("https://api.example.com")

    @Test
    fun forwardsDomainArgumentsAndCountsCalls() = runTest {
        val forwardedSetups = mutableListOf<ApiSetupProtocol>()
        val session = MockedNetworkSession(UserProviderSpyTest::class.java) { setup ->
            forwardedSetups += setup
            UserApiFixtures.fileNameFor(setup)
        }
        val spy = UserProviderSpy(UserApiProvider(baseUrl, session))
        val input = NewUser(name = "Avery")

        val fetched = spy.getUser(id = 42)
        val created = spy.createUser(input)

        assertEquals(User(id = 1, name = "Taylor"), fetched)
        assertEquals(User(id = 2, name = "Jordan"), created)
        spy.assertExpectedInvocations(listOf(MethodKey.GetUser to 1, MethodKey.CreateUser to 1))
        assertEquals(2, forwardedSetups.size)
        val get = assertIs<UserApiSetup.GetUser>(forwardedSetups[0]).request
        assertEquals("/users/42", get.url.path)
        val create = assertIs<UserApiSetup.CreateUser>(forwardedSetups[1]).request
        assertEquals("/users", create.url.path)
        assertEquals(
            buildJsonObject { put("name", input.name) },
            Json.parseToJsonElement(requireNotNull(create.body).decodeToString()),
        )
    }

    @Test
    fun countsFailedCallsAndConsumesFailuresInOrderForEachMethod() = runTest {
        val forwardedSetups = mutableListOf<ApiSetupProtocol>()
        val session = MockedNetworkSession(UserProviderSpyTest::class.java) { setup ->
            forwardedSetups += setup
            UserApiFixtures.fileNameFor(setup)
        }
        val spy = UserProviderSpy(UserApiProvider(baseUrl, session))
        val createFailure = IllegalStateException("Queued create")
        val firstGetFailure = IllegalArgumentException("First queued get")
        val secondGetFailure = IOException("Second queued get")
        spy.enqueueFailures(
            listOf(
                PlannedFailure(MethodKey.CreateUser, createFailure),
                PlannedFailure(MethodKey.GetUser, firstGetFailure),
                PlannedFailure(MethodKey.GetUser, secondGetFailure),
            ),
        )

        assertSame(firstGetFailure, assertFailsWith<IllegalArgumentException> { spy.getUser(id = 999) })
        // Unlisted CreateUser must still have zero calls despite its earlier queued failure.
        spy.assertExpectedInvocations(listOf(MethodKey.GetUser to 1))
        assertEquals(listOf(MethodKey.CreateUser, MethodKey.GetUser), spy.failingMethods.map { it.method })
        assertSame(secondGetFailure, assertFailsWith<IOException> { spy.getUser(id = 998) })
        assertTrue(forwardedSetups.isEmpty())

        assertEquals(User(id = 1, name = "Taylor"), spy.getUser(id = 1))
        assertSame(
            createFailure,
            assertFailsWith<IllegalStateException> { spy.createUser(NewUser(name = "Jordan")) },
        )
        spy.assertExpectedInvocations(listOf(MethodKey.GetUser to 3, MethodKey.CreateUser to 1))
        assertTrue(spy.failingMethods.isEmpty())
        assertEquals("/users/1", forwardedSetups.single().request.url.path)

        assertEquals(User(id = 2, name = "Jordan"), spy.createUser(NewUser(name = "Jordan")))
        spy.assertExpectedInvocations(listOf(MethodKey.GetUser to 3, MethodKey.CreateUser to 2))
        assertEquals(2, forwardedSetups.size)
    }
}
