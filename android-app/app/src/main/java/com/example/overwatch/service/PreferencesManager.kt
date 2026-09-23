package com.example.overwatch.service

import android.content.Context
import android.content.SharedPreferences
import com.example.overwatch.model.ServerItem
import com.example.overwatch.model.ServerType
import com.example.overwatch.model.SshProfile
import org.json.JSONArray
import org.json.JSONObject

class PreferencesManager(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("overwatch_prefs", Context.MODE_PRIVATE)

    companion object {
        private const val KEY_GEMINI_API_KEY = "gemini_api_key"
        private const val KEY_DEFAULT_HOST = "default_host"
        private const val KEY_AUTO_REFRESH = "auto_refresh"
        private const val KEY_REFRESH_INTERVAL = "refresh_interval"
        private const val KEY_CUSTOM_SERVERS = "custom_servers"
        private const val KEY_SSH_PROFILES = "ssh_profiles"
        private const val KEY_VNC_HOST = "vnc_bridge_host"
        private const val KEY_VNC_PORT = "vnc_bridge_port"
        private const val KEY_AUTO_UPDATE = "auto_update_on_launch"
    }

    var geminiApiKey: String
        get() = prefs.getString(KEY_GEMINI_API_KEY, "") ?: ""
        set(value) = prefs.edit().putString(KEY_GEMINI_API_KEY, value).apply()

    var defaultHost: String
        get() = prefs.getString(KEY_DEFAULT_HOST, "therealbonz.com") ?: "therealbonz.com"
        set(value) = prefs.edit().putString(KEY_DEFAULT_HOST, value).apply()

    var vncBridgeHost: String
        get() {
            val h = prefs.getString(KEY_VNC_HOST, "10.0.0.225") ?: "10.0.0.225"
            return if (h == "10.0.0.189") "10.0.0.225" else h
        }
        set(value) = prefs.edit().putString(KEY_VNC_HOST, value).apply()

    var vncBridgePort: Int
        get() = prefs.getInt(KEY_VNC_PORT, 5901)
        set(value) = prefs.edit().putInt(KEY_VNC_PORT, value).apply()

    var autoUpdateOnLaunch: Boolean
        get() = prefs.getBoolean(KEY_AUTO_UPDATE, true)
        set(value) = prefs.edit().putBoolean(KEY_AUTO_UPDATE, value).apply()

    var autoRefresh: Boolean
        get() = prefs.getBoolean(KEY_AUTO_REFRESH, true)
        set(value) = prefs.edit().putBoolean(KEY_AUTO_REFRESH, value).apply()

    var refreshIntervalSeconds: Int
        get() = prefs.getInt(KEY_REFRESH_INTERVAL, 15)
        set(value) = prefs.edit().putInt(KEY_REFRESH_INTERVAL, value).apply()

    fun getCustomServers(): List<ServerItem> {
        val raw = prefs.getString(KEY_CUSTOM_SERVERS, null) ?: return emptyList()
        val list = mutableListOf<ServerItem>()
        try {
            val arr = JSONArray(raw)
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                val typeStr = obj.optString("type", ServerType.HTTP.name)
                val type = runCatching { ServerType.valueOf(typeStr) }.getOrDefault(ServerType.HTTP)
                list.add(
                    ServerItem(
                        id = obj.optString("id", java.util.UUID.randomUUID().toString()),
                        name = obj.optString("name", "Server"),
                        host = obj.optString("host", defaultHost),
                        port = obj.optInt("port", 80),
                        type = type,
                        checkPath = obj.optString("checkPath", "")
                    )
                )
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return list
    }

    fun saveCustomServers(servers: List<ServerItem>) {
        val arr = JSONArray()
        for (s in servers) {
            val obj = JSONObject()
            obj.put("id", s.id)
            obj.put("name", s.name)
            obj.put("host", s.host)
            obj.put("port", s.port)
            obj.put("type", s.type.name)
            obj.put("checkPath", s.checkPath)
            arr.put(obj)
        }
        prefs.edit().putString(KEY_CUSTOM_SERVERS, arr.toString()).apply()
    }

    fun getSshProfiles(): List<SshProfile> {
        val raw = prefs.getString(KEY_SSH_PROFILES, null)
        if (raw.isNullOrEmpty()) {
            return listOf(
                SshProfile(
                    id = "default-bonz",
                    name = "therealbonz.com (bonz)",
                    host = defaultHost,
                    port = 22,
                    username = "bonz"
                )
            )
        }
        val list = mutableListOf<SshProfile>()
        try {
            val arr = JSONArray(raw)
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                list.add(
                    SshProfile(
                        id = obj.optString("id", java.util.UUID.randomUUID().toString()),
                        name = obj.optString("name", "Server"),
                        host = obj.optString("host", defaultHost),
                        port = obj.optInt("port", 22),
                        username = obj.optString("username", "bonz"),
                        password = obj.optString("password", ""),
                        privateKey = obj.optString("privateKey", "")
                    )
                )
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return if (list.isEmpty()) listOf(
            SshProfile(
                id = "default-bonz",
                name = "therealbonz.com (bonz)",
                host = defaultHost,
                port = 22,
                username = "bonz"
            )
        ) else list
    }

    fun saveSshProfiles(profiles: List<SshProfile>) {
        val arr = JSONArray()
        for (p in profiles) {
            val obj = JSONObject()
            obj.put("id", p.id)
            obj.put("name", p.name)
            obj.put("host", p.host)
            obj.put("port", p.port)
            obj.put("username", p.username)
            obj.put("password", p.password)
            obj.put("privateKey", p.privateKey)
            arr.put(obj)
        }
        prefs.edit().putString(KEY_SSH_PROFILES, arr.toString()).apply()
    }
}
