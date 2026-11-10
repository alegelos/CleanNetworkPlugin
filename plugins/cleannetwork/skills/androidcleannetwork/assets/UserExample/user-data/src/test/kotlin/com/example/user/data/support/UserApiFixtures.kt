package com.example.user.data.support

import com.alegelos.androidcleannetwork.ApiSetupProtocol
import com.alegelos.androidcleannetwork.testing.MockedNetworkSession
import com.example.user.data.UserApiSetup

// Routing stays in test code and receives the same Setup that production transport would use.
internal object UserApiFixtures {
    fun fileNameFor(setup: ApiSetupProtocol): String? = when (setup) {
        is UserApiSetup.GetUser -> "fixtures/GetUser.json"
        is UserApiSetup.CreateUser -> "fixtures/CreateUser.json"
        else -> null
    }

    fun session(): MockedNetworkSession = MockedNetworkSession(
        fixtureAnchor = UserApiFixtures::class.java,
        fixtureFileNameFor = ::fileNameFor,
    )
}
