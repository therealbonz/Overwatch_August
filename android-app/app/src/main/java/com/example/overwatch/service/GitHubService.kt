package com.example.overwatch.service

import com.example.overwatch.model.GitHubRepo
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class GitHubService {
    private val client = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    suspend fun fetchRepositories(username: String = "therealbonz"): List<GitHubRepo> = withContext(Dispatchers.IO) {
        val url = "https://api.github.com/users/$username/repos?per_page=100&sort=updated"
        val request = Request.Builder()
            .url(url)
            .header("Accept", "application/vnd.github+json")
            .header("User-Agent", "Overwatch-Mobile-Client")
            .build()

        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw Exception("Failed to fetch repos: HTTP ${response.code}")
            }
            val body = response.body?.string() ?: "[]"
            val arr = JSONArray(body)
            val list = mutableListOf<GitHubRepo>()

            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                val rawDesc = obj.optString("description", "")
                val cleanDesc = if (rawDesc.isBlank() || rawDesc == "null") "No description provided." else rawDesc
                val rawLang = obj.optString("language", "")
                val cleanLang = if (rawLang.isBlank() || rawLang == "null") "Code" else rawLang

                list.add(
                    GitHubRepo(
                        id = obj.optLong("id"),
                        name = obj.optString("name", "Unknown"),
                        fullName = obj.optString("full_name", ""),
                        description = cleanDesc,
                        language = cleanLang,
                        stars = obj.optInt("stargazers_count", 0),
                        forks = obj.optInt("forks_count", 0),
                        isPrivate = obj.optBoolean("private", false),
                        htmlUrl = obj.optString("html_url", ""),
                        cloneUrl = obj.optString("clone_url", ""),
                        updatedAt = obj.optString("updated_at", ""),
                        defaultBranch = obj.optString("default_branch", "main")
                    )
                )
            }
            list
        }
    }

    suspend fun fetchReadme(repoFullName: String): String = withContext(Dispatchers.IO) {
        val url = "https://api.github.com/repos/$repoFullName/readme"
        val request = Request.Builder()
            .url(url)
            .header("Accept", "application/vnd.github.raw+json")
            .header("User-Agent", "Overwatch-Mobile-Client")
            .build()

        try {
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    response.body?.string() ?: "No README found."
                } else {
                    "No README.md found in this repository."
                }
            }
        } catch (e: Exception) {
            "Error loading README: ${e.localizedMessage}"
        }
    }

    suspend fun fetchFileTree(repoFullName: String, path: String = ""): List<String> = withContext(Dispatchers.IO) {
        val url = "https://api.github.com/repos/$repoFullName/contents/$path"
        val request = Request.Builder()
            .url(url)
            .header("Accept", "application/vnd.github+json")
            .header("User-Agent", "Overwatch-Mobile-Client")
            .build()

        try {
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "[]"
                    val arr = JSONArray(body)
                    val files = mutableListOf<String>()
                    for (i in 0 until arr.length()) {
                        val item = arr.getJSONObject(i)
                        val name = item.optString("name")
                        val type = item.optString("type")
                        files.add(if (type == "dir") "$name/" else name)
                    }
                    files
                } else {
                    emptyList()
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }
}
