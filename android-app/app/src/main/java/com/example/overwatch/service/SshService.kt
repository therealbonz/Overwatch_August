package com.example.overwatch.service

import com.example.overwatch.model.SshProfile
import com.jcraft.jsch.ChannelExec
import com.jcraft.jsch.JSch
import com.jcraft.jsch.Session
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStreamReader

class SshService {

    suspend fun executeCommand(
        profile: SshProfile,
        command: String,
        onOutput: suspend (String) -> Unit
    ): Result<Int> = withContext(Dispatchers.IO) {
        var session: Session? = null
        var channel: ChannelExec? = null

        try {
            val jsch = JSch()

            if (profile.privateKey.isNotBlank()) {
                val keyBytes = profile.privateKey.toByteArray(Charsets.UTF_8)
                jsch.addIdentity("custom_key", keyBytes, null, null)
            }

            session = jsch.getSession(profile.username, profile.host, profile.port)
            if (profile.password.isNotBlank()) {
                session.setPassword(profile.password)
            }

            val config = java.util.Properties()
            config["StrictHostKeyChecking"] = "no"
            session.setConfig(config)
            session.timeout = 8000

            onOutput("🔌 Connecting to ${profile.username}@${profile.host}:${profile.port}...")
            session.connect(7000)
            onOutput("✅ SSH Session Authenticated. Executing command:\n$ $command\n")

            channel = session.openChannel("exec") as ChannelExec
            channel.setCommand(command)

            val inputStream = channel.inputStream
            val errorStream = channel.errStream

            channel.connect(5000)

            val reader = BufferedReader(InputStreamReader(inputStream))
            val errReader = BufferedReader(InputStreamReader(errorStream))

            var line: String?
            while (reader.readLine().also { line = it } != null) {
                onOutput(line ?: "")
            }

            while (errReader.readLine().also { line = it } != null) {
                onOutput("⚠️ ${line ?: ""}")
            }

            while (!channel.isClosed) {
                Thread.sleep(100)
            }

            val exitCode = channel.exitStatus
            onOutput("\n🏁 Process exited with code $exitCode")
            Result.success(exitCode)

        } catch (e: Exception) {
            val err = "❌ SSH Error: ${e.localizedMessage ?: e.javaClass.simpleName}"
            onOutput(err)
            Result.failure(e)
        } finally {
            channel?.disconnect()
            session?.disconnect()
        }
    }

    suspend fun cloneRepository(
        profile: SshProfile,
        repoUrl: String,
        targetDir: String = "",
        onOutput: suspend (String) -> Unit
    ): Result<Int> {
        val cleanUrl = repoUrl.trim()
        val dir = if (targetDir.isNotBlank()) targetDir.trim() else cleanUrl.substringAfterLast("/").removeSuffix(".git")
        val cmd = "cd /var/www 2>/dev/null || cd ~ ; git clone $cleanUrl $dir && ls -la $dir"
        return executeCommand(profile, cmd, onOutput)
    }

    suspend fun createDirectory(
        profile: SshProfile,
        dirName: String,
        onOutput: suspend (String) -> Unit
    ): Result<Int> {
        val safeName = dirName.replace("\"", "\\\"").trim()
        val cmd = "mkdir -p /var/www/$safeName 2>/dev/null || mkdir -p ~/$safeName ; ls -ld /var/www/$safeName 2>/dev/null || ls -ld ~/$safeName"
        return executeCommand(profile, cmd, onOutput)
    }

    suspend fun addService(
        profile: SshProfile,
        serviceName: String,
        execCommand: String,
        onOutput: suspend (String) -> Unit
    ): Result<Int> {
        val cleanName = serviceName.trim().replace(" ", "-").lowercase()
        val cmd = """
            echo "Creating supervisor script for $cleanName..."
            mkdir -p ~/services/$cleanName
            cat << 'EOF' > ~/services/$cleanName/run.sh
            #!/bin/bash
            $execCommand
            EOF
            chmod +x ~/services/$cleanName/run.sh
            echo "Service runner created at ~/services/$cleanName/run.sh"
            echo "Starting service in background..."
            nohup ~/services/$cleanName/run.sh > ~/services/$cleanName/output.log 2>&1 &
            sleep 1
            ps aux | grep "$cleanName" | grep -v grep
        """.trimIndent()
        return executeCommand(profile, cmd, onOutput)
    }
}
