package com.example.overwatch.service

import com.example.overwatch.model.ChatMessage
import com.example.overwatch.model.GitHubRepo
import com.example.overwatch.model.MessageSender
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

enum class AnalysisMode(val title: String, val promptPrefix: String) {
    ARCHITECTURE(
        "Architecture & Stack Breakdown",
        "Analyze the following GitHub repository architecture, directory structure, tech stack, and key modules. Provide a clear, developer-focused breakdown:"
    ),
    SECURITY_AUDIT(
        "Security & Vulnerability Audit",
        "Perform a security review of this project. Identify potential security considerations, dependency hygiene, credentials risk, and production hardening recommendations:"
    ),
    REFACTOR_IDEAS(
        "Refactoring & Feature Proposals",
        "Suggest 3 high-impact feature enhancements and 2 architectural refactoring opportunities for this project:"
    ),
    QUICK_SUMMARY(
        "Executive Summary",
        "Provide a concise 3-paragraph executive summary of this project, its target audience, and primary capabilities:"
    )
}

class GeminiService(private val prefs: PreferencesManager) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    suspend fun analyzeRepository(
        repo: GitHubRepo,
        readme: String,
        files: List<String>,
        mode: AnalysisMode
    ): String = withContext(Dispatchers.IO) {
        val apiKey = prefs.geminiApiKey.trim()
        if (apiKey.isEmpty()) {
            return@withContext "⚠️ **Gemini API Key Missing**\n\nPlease add your Gemini API Key in the **Settings** tab to enable live AI analysis on your repositories.\n\n*Repository Context Cached:*\n- **Name:** ${repo.fullName}\n- **Language:** ${repo.language}\n- **Stars:** ${repo.stars} | **Forks:** ${repo.forks}\n- **Files:** ${files.take(15).joinToString(", ")}"
        }

        val fileListStr = files.take(30).joinToString("\n- ")
        val readmeTruncated = if (readme.length > 2500) readme.substring(0, 2500) + "... [truncated]" else readme

        val prompt = """
            ${mode.promptPrefix}
            
            Repository: ${repo.fullName}
            Description: ${repo.description}
            Primary Language: ${repo.language}
            Stars: ${repo.stars}, Forks: ${repo.forks}
            
            Root Files / Folders:
            - $fileListStr
            
            README Excerpt:
            $readmeTruncated
        """.trimIndent()

        callGeminiApi(apiKey, prompt)
    }

    suspend fun askQuestion(
        repo: GitHubRepo?,
        userQuestion: String,
        chatHistory: List<ChatMessage>
    ): String = withContext(Dispatchers.IO) {
        val apiKey = prefs.geminiApiKey.trim()
        if (apiKey.isEmpty()) {
            return@withContext "⚠️ Please configure your Gemini API Key in the **Settings** tab to chat with Gemini AI."
        }

        val repoInfo = if (repo != null) {
            "Active Repository Context: ${repo.fullName} (${repo.language}). Description: ${repo.description}\n\n"
        } else {
            "No specific repository selected. You are assisting developer @therealbonz.\n\n"
        }

        val prompt = "$repoInfo User Question: $userQuestion"
        callGeminiApi(apiKey, prompt)
    }

    private fun callGeminiApi(apiKey: String, userText: String): String {
        val models = listOf("gemini-2.0-flash", "gemini-1.5-flash")
        var lastError = "Failed to connect to Gemini API."

        for (model in models) {
            try {
                val url = "https://generativelanguage.googleapis.com/v1beta/models/$model:generateContent?key=$apiKey"
                
                val partsArray = JSONArray()
                partsArray.put(JSONObject().put("text", userText))

                val contentObj = JSONObject()
                contentObj.put("role", "user")
                contentObj.put("parts", partsArray)

                val contentsArray = JSONArray()
                contentsArray.put(contentObj)

                val payload = JSONObject()
                payload.put("contents", contentsArray)

                val requestBody = payload.toString().toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url(url)
                    .post(requestBody)
                    .build()

                client.newCall(request).execute().use { response ->
                    val bodyString = response.body?.string() ?: ""
                    if (!response.isSuccessful) {
                        lastError = "Gemini API Error ($model - ${response.code}): $bodyString"
                        return@use
                    }

                    val json = JSONObject(bodyString)
                    val candidates = json.optJSONArray("candidates")
                    if (candidates != null && candidates.length() > 0) {
                        val firstCandidate = candidates.getJSONObject(0)
                        val content = firstCandidate.optJSONObject("content")
                        val parts = content?.optJSONArray("parts")
                        if (parts != null && parts.length() > 0) {
                            return parts.getJSONObject(0).optString("text", "No response text received.")
                        }
                    }
                    lastError = "Received empty response from Gemini ($model)."
                }
            } catch (e: Exception) {
                lastError = "Connection error ($model): ${e.localizedMessage}"
            }
        }

        return "⚠️ $lastError"
    }
}
