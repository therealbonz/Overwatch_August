package com.example.overwatch.model

enum class ServerType(val displayName: String, val defaultPort: Int) {
    FTP("FTP Server", 21),
    RUBY("Ruby (Puma/Rails)", 3000),
    REACT("React Frontend", 80),
    PYTHON("Python (FastAPI)", 8080),
    HTTP("Custom HTTP", 80),
    TCP("Custom TCP", 22)
}

data class ServerItem(
    val id: String,
    val name: String,
    val host: String,
    val port: Int,
    val type: ServerType,
    val checkPath: String = "",
    val isOnline: Boolean = false,
    val latencyMs: Long = -1,
    val lastChecked: Long = 0,
    val statusMessage: String = "Pending check...",
    val details: String = ""
)

data class GitHubRepo(
    val id: Long,
    val name: String,
    val fullName: String,
    val description: String,
    val language: String,
    val stars: Int,
    val forks: Int,
    val isPrivate: Boolean,
    val htmlUrl: String,
    val cloneUrl: String,
    val updatedAt: String,
    val defaultBranch: String = "main"
)

enum class MessageSender {
    USER,
    GEMINI,
    SYSTEM
}

data class ChatMessage(
    val id: String = java.util.UUID.randomUUID().toString(),
    val sender: MessageSender,
    val text: String,
    val timestamp: Long = System.currentTimeMillis()
)

data class SshProfile(
    val id: String = java.util.UUID.randomUUID().toString(),
    val name: String,
    val host: String,
    val port: Int = 22,
    val username: String = "bonz",
    val password: String = "",
    val privateKey: String = ""
)
