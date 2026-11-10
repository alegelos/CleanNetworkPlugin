package com.example.user.data

import com.alegelos.androidcleannetwork.ApiProvider
import com.alegelos.androidcleannetwork.DefaultNetworkSession
import com.alegelos.androidcleannetwork.NetworkSessionProtocol
import com.example.user.domain.NewUser
import com.example.user.domain.User
import com.example.user.domain.UserProviderProtocol
import java.net.URL
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

class UserApiProvider(
    override val baseUrl: URL,
    override val session: NetworkSessionProtocol = DefaultNetworkSession,
) : ApiProvider, UserProviderProtocol {
    private val json = Json { ignoreUnknownKeys = true }

    override suspend fun getUser(id: Int): User {
        val setup = UserApiSetup.GetUser(baseUrl = baseUrl, id = id)
        val response = session.dataFor(setup)
        return json.decodeFromString<UserResponse>(response.data.decodeToString()).domain
    }

    override suspend fun createUser(user: NewUser): User {
        val dto = CreateUserDTO(user)
        val body = json.encodeToString(dto).encodeToByteArray()
        val setup = UserApiSetup.CreateUser(baseUrl = baseUrl, body = body)
        val response = session.dataFor(setup)
        return json.decodeFromString<UserResponse>(response.data.decodeToString()).domain
    }
}
