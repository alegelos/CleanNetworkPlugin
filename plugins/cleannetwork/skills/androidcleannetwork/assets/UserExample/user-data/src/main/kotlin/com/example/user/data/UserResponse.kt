package com.example.user.data

import com.example.user.domain.User
import kotlinx.serialization.Serializable

@Serializable
internal data class UserResponse(
    val id: Int,
    val name: String,
) {
    val domain: User
        get() = User(id = id, name = name)
}
