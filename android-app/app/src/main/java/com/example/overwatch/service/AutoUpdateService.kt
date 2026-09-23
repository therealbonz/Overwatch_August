package com.example.overwatch.service

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.widget.Toast
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.TimeUnit

data class UpdateInfo(
    val versionCode: Int,
    val versionName: String,
    val downloadUrl: String,
    val changelog: String
)

class AutoUpdateService(private val context: Context) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    fun getCurrentVersionCode(): Long {
        return try {
            val pInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                context.packageManager.getPackageInfo(context.packageName, PackageManager.PackageInfoFlags.of(0))
            } else {
                @Suppress("DEPRECATION")
                context.packageManager.getPackageInfo(context.packageName, 0)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                pInfo.longVersionCode
            } else {
                @Suppress("DEPRECATION")
                pInfo.versionCode.toLong()
            }
        } catch (e: Exception) {
            1L
        }
    }

    fun getCurrentVersionName(): String {
        return try {
            val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            pInfo.versionName ?: "1.0"
        } catch (e: Exception) {
            "1.0"
        }
    }

    suspend fun checkUpdate(serverHost: String): UpdateInfo? = withContext(Dispatchers.IO) {
        val url = "http://$serverHost:5901/api/app/version"
        try {
            val req = Request.Builder().url(url).build()
            val resp = client.newCall(req).execute()
            if (!resp.isSuccessful) return@withContext null
            val body = resp.body?.string() ?: return@withContext null
            val json = JSONObject(body)

            val remoteVersionCode = json.optInt("versionCode", 1)
            val remoteVersionName = json.optString("versionName", "1.0")
            var dlUrl = json.optString("downloadUrl", "http://$serverHost:5901/api/app/latest.apk")
            if (dlUrl.startsWith("/")) {
                dlUrl = "http://$serverHost:5901$dlUrl"
            }
            val changelog = json.optString("changelog", "Bug fixes and improvements")

            val currentCode = getCurrentVersionCode()
            if (remoteVersionCode > currentCode) {
                UpdateInfo(remoteVersionCode, remoteVersionName, dlUrl, changelog)
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    suspend fun downloadAndInstall(
        downloadUrl: String,
        onProgress: (Float) -> Unit,
        onError: (String) -> Unit
    ) = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url(downloadUrl).build()
            val resp = client.newCall(req).execute()
            if (!resp.isSuccessful) {
                withContext(Dispatchers.Main) { onError("Download failed: HTTP ${resp.code}") }
                return@withContext
            }

            val body = resp.body ?: run {
                withContext(Dispatchers.Main) { onError("Empty response body") }
                return@withContext
            }

            val totalBytes = body.contentLength()
            val apkFile = File(context.cacheDir, "overwatch_update.apk")
            if (apkFile.exists()) apkFile.delete()

            body.byteStream().use { input ->
                FileOutputStream(apkFile).use { output ->
                    val buffer = ByteArray(8192)
                    var bytesRead: Int
                    var totalRead: Long = 0
                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        output.write(buffer, 0, bytesRead)
                        totalRead += bytesRead
                        if (totalBytes > 0) {
                            val prog = totalRead.toFloat() / totalBytes
                            withContext(Dispatchers.Main) { onProgress(prog) }
                        }
                    }
                    output.flush()
                }
            }

            withContext(Dispatchers.Main) {
                installApk(apkFile)
            }
        } catch (e: Exception) {
            withContext(Dispatchers.Main) {
                onError(e.message ?: "Unknown error downloading update")
            }
        }
    }

    private fun installApk(apkFile: File) {
        try {
            val contentUri: Uri = FileProvider.getUriForFile(
                context,
                "${context.packageName}.fileprovider",
                apkFile
            )

            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(contentUri, "application/vnd.android.package-archive")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(context, "Cannot launch installer: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }
}
