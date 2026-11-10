package com.example.user.data

import com.example.user.domain.NewUser
import kotlinx.serialization.Serializable

@Serializable
internal data class CreateUserDTO(
    val name: String,
) {
    constructor(user: NewUser) : this(name = user.name)
}
