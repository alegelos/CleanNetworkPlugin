package com.example.user.domain

interface UserProviderProtocol {
    suspend fun getUser(id: Int): User

    suspend fun createUser(user: NewUser): User
}
