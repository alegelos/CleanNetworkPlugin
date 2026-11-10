package com.example.user.data.support

import com.alegelos.androidcleannetwork.testing.PlannedFailure
import com.alegelos.androidcleannetwork.testing.ProviderSpyProtocol
import com.example.user.domain.NewUser
import com.example.user.domain.User
import com.example.user.domain.UserProviderProtocol

// One instance per test. This mutable spy is not intended for concurrent callers.
internal class UserProviderSpy(
    private val wrapped: UserProviderProtocol,
) : UserProviderProtocol, ProviderSpyProtocol<UserProviderSpy.MethodKey> {
    enum class MethodKey { GetUser, CreateUser }

    override val allMethods = MethodKey.entries.toTypedArray()
    override var invocationsCount = mutableMapOf<MethodKey, Int>()
    override var failingMethods = mutableListOf<PlannedFailure<MethodKey>>()

    override suspend fun getUser(id: Int): User {
        increment(MethodKey.GetUser)
        validateFailingMethods(MethodKey.GetUser)
        return wrapped.getUser(id)
    }

    override suspend fun createUser(user: NewUser): User {
        increment(MethodKey.CreateUser)
        validateFailingMethods(MethodKey.CreateUser)
        return wrapped.createUser(user)
    }
}
