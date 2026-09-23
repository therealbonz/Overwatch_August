package com.example.overwatch.service

import com.example.overwatch.model.ServerItem
import com.example.overwatch.model.ServerType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.TimeUnit

class ServerProbeService {
    private val client = OkHttpClient.Builder()
        .connectTimeout(3500, TimeUnit.MILLISECONDS)
        .readTimeout(3500, TimeUnit.MILLISECONDS)
        .followRedirects(true)
        .build()

    suspend fun probeServer(server: ServerItem): ServerItem = withContext(Dispatchers.IO) {
        val startTime = System.currentTimeMillis()
        try {
            when (server.type) {
                ServerType.FTP, ServerType.TCP -> {
                    probeTcpSocket(server, startTime)
                }
                ServerType.RUBY, ServerType.REACT, ServerType.PYTHON, ServerType.HTTP -> {
                    probeHttpEndpoint(server, startTime)
                }
            }
        } catch (e: Exception) {
            server.copy(
                isOnline = false,
                latencyMs = -1,
                lastChecked = System.currentTimeMillis(),
                statusMessage = "Offline (${e.localizedMessage ?: "Connection refused"})",
                details = e.javaClass.simpleName
            )
        }
    }

    private fun probeTcpSocket(server: ServerItem, startTime: Long): ServerItem {
        Socket().use { socket ->
            socket.connect(InetSocketAddress(server.host, server.port), 3000)
            val latency = System.currentTimeMillis() - startTime
            var banner = "TCP Connection Established"
            
            // Try to read greeting banner if server speaks first (e.g. FTP 220 banner)
            try {
                socket.soTimeout = 800
                val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
                val line = reader.readLine()
                if (!line.isNullOrBlank()) {
                    banner = line.trim()
                }
            } catch (_: Exception) {
                // Ignore timeout reading banner, socket connection itself succeeded
            }

            return server.copy(
                isOnline = true,
                latencyMs = latency,
                lastChecked = System.currentTimeMillis(),
                statusMessage = "Online (${latency}ms)",
                details = banner
            )
        }
    }

    private fun probeHttpEndpoint(server: ServerItem, startTime: Long): ServerItem {
        val scheme = if (server.port == 443) "https" else "http"
        val portPart = if ((server.port == 80 && scheme == "http") || (server.port == 443 && scheme == "https")) {
            ""
        } else {
            ":${server.port}"
        }
        val cleanPath = if (server.checkPath.isNotEmpty() && !server.checkPath.startsWith("/")) {
            "/${server.checkPath}"
        } else {
            server.checkPath
        }
        val url = "$scheme://${server.host}$portPart$cleanPath"

        val request = Request.Builder()
            .url(url)
            .header("User-Agent", "Overwatch-Mobile-Monitor/1.0")
            .get()
            .build()

        client.newCall(request).execute().use { response ->
            val latency = System.currentTimeMillis() - startTime
            val code = response.code
            val isSuccess = code in 200..499 // Any HTTP response code means web server process is actively responding

            var details = "HTTP $code ${response.message}"
            try {
                val bodyStr = response.body?.string() ?: ""
                if (bodyStr.startsWith("{") && bodyStr.contains("status")) {
                    val json = JSONObject(bodyStr)
                    if (json.has("status")) {
                        details += " • Status: ${json.getString("status")}"
                    }
                    if (json.has("platform")) {
                        details += " • ${json.getString("platform")}"
                    }
                }
            } catch (_: Exception) {}

            return server.copy(
                isOnline = isSuccess,
                latencyMs = latency,
                lastChecked = System.currentTimeMillis(),
                statusMessage = if (isSuccess) "Active (${code}) • ${latency}ms" else "HTTP $code",
                details = details
            )
        }
    }
}
