package com.example.overwatch.ui.screens

import android.os.Build
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.overwatch.service.GeminiService
import com.example.overwatch.service.PreferencesManager
import com.example.overwatch.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    prefs: PreferencesManager,
    geminiService: GeminiService
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    var apiKey by remember { mutableStateOf(prefs.geminiApiKey) }
    var showApiKey by remember { mutableStateOf(false) }
    var isTestingKey by remember { mutableStateOf(false) }
    var keyTestResult by remember { mutableStateOf<String?>(null) }

    var host by remember { mutableStateOf(prefs.defaultHost) }
    var autoRefresh by remember { mutableStateOf(prefs.autoRefresh) }
    var refreshInterval by remember { mutableStateOf(prefs.refreshIntervalSeconds) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings & Preferences", fontWeight = FontWeight.Bold, color = CyberText, fontSize = 18.sp) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = CyberSurface)
            )
        },
        containerColor = CyberBg,
        contentWindowInsets = WindowInsets(0.dp)
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Gemini AI API Configuration Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CyberSurface),
                shape = RoundedCornerShape(12.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, CyberAccent.copy(alpha = 0.4f))
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.AutoAwesome, contentDescription = null, tint = CyberAccent)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Gemini AI API Configuration", fontWeight = FontWeight.Bold, fontSize = 15.sp, color = CyberText)
                    }

                    Text(
                        "Enter your Google Gemini API key to enable repository code analysis, architecture breakdown, and interactive AI chat.",
                        fontSize = 12.sp,
                        color = CyberTextMuted
                    )

                    OutlinedTextField(
                        value = apiKey,
                        onValueChange = {
                            apiKey = it
                            keyTestResult = null
                        },
                        label = { Text("Gemini API Key") },
                        placeholder = { Text("AIzaSy...") },
                        singleLine = true,
                        visualTransformation = if (showApiKey) VisualTransformation.None else PasswordVisualTransformation(),
                        trailingIcon = {
                            IconButton(onClick = { showApiKey = !showApiKey }) {
                                Icon(
                                    if (showApiKey) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                    contentDescription = "Toggle Key",
                                    tint = CyberTextMuted
                                )
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = CyberText,
                            unfocusedTextColor = CyberText,
                            focusedBorderColor = CyberAccent,
                            unfocusedBorderColor = CyberBorder
                        )
                    )

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = {
                                prefs.geminiApiKey = apiKey.trim()
                                Toast.makeText(context, "API Key Saved!", Toast.LENGTH_SHORT).show()
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = CyberAccent, contentColor = CyberBg),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("Save Key", fontWeight = FontWeight.SemiBold)
                        }

                        OutlinedButton(
                            onClick = {
                                if (apiKey.isBlank()) {
                                    Toast.makeText(context, "Please enter an API key first", Toast.LENGTH_SHORT).show()
                                    return@OutlinedButton
                                }
                                isTestingKey = true
                                keyTestResult = null
                                prefs.geminiApiKey = apiKey.trim()
                                coroutineScope.launch {
                                    val res = geminiService.askQuestion(null, "Say 'Hello from Gemini!'", emptyList())
                                    isTestingKey = false
                                    keyTestResult = if (res.startsWith("⚠️")) res else "✅ Connected successfully: $res"
                                }
                            },
                            enabled = !isTestingKey,
                            shape = RoundedCornerShape(8.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
                        ) {
                            if (isTestingKey) {
                                CircularProgressIndicator(modifier = Modifier.size(16.dp), color = CyberAccent, strokeWidth = 2.dp)
                            } else {
                                Text("Test Key", color = CyberText)
                            }
                        }
                    }

                    if (keyTestResult != null) {
                        Text(
                            text = keyTestResult!!,
                            fontSize = 12.sp,
                            color = if (keyTestResult!!.startsWith("✅")) CyberSecondary else CyberError
                        )
                    }
                }
            }

            // Server Host & Network Settings
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CyberSurface),
                shape = RoundedCornerShape(12.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Dns, contentDescription = null, tint = CyberPrimary)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Server Target & Network", fontWeight = FontWeight.Bold, fontSize = 15.sp, color = CyberText)
                    }

                    OutlinedTextField(
                        value = host,
                        onValueChange = {
                            host = it
                            prefs.defaultHost = it.trim()
                        },
                        label = { Text("Default Host / Domain") },
                        placeholder = { Text("therealbonz.com") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = CyberText,
                            unfocusedTextColor = CyberText,
                            focusedBorderColor = CyberPrimary,
                            unfocusedBorderColor = CyberBorder
                        )
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text("Automatic Periodic Ping", fontSize = 13.sp, color = CyberText, fontWeight = FontWeight.Medium)
                            Text("Ping server probes in the background", fontSize = 11.sp, color = CyberTextMuted)
                        }
                        Switch(
                            checked = autoRefresh,
                            onCheckedChange = {
                                autoRefresh = it
                                prefs.autoRefresh = it
                            },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = CyberPrimary,
                                checkedTrackColor = CyberPrimary.copy(alpha = 0.3f)
                            )
                        )
                    }
                }
            }

            // Antigravity VNC Bridge & Auto-Update Settings
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CyberSurface),
                shape = RoundedCornerShape(12.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, CyberPrimary.copy(alpha = 0.4f))
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.ConnectedTv, contentDescription = null, tint = CyberPrimary)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Antigravity VNC & Auto-Update", fontWeight = FontWeight.Bold, fontSize = 15.sp, color = CyberText)
                    }

                    var vncHostInput by remember { mutableStateOf(prefs.vncBridgeHost) }
                    OutlinedTextField(
                        value = vncHostInput,
                        onValueChange = {
                            vncHostInput = it
                            prefs.vncBridgeHost = it.trim()
                        },
                        label = { Text("Antigravity PC Host IP") },
                        placeholder = { Text("10.0.0.189") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text("Auto-Update on Launch", fontSize = 13.sp, color = CyberText, fontWeight = FontWeight.Medium)
                            Text("Automatically check and prompt to install new builds", fontSize = 11.sp, color = CyberTextMuted)
                        }
                        var autoUp by remember { mutableStateOf(prefs.autoUpdateOnLaunch) }
                        Switch(
                            checked = autoUp,
                            onCheckedChange = {
                                autoUp = it
                                prefs.autoUpdateOnLaunch = it
                            },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = CyberPrimary,
                                checkedTrackColor = CyberPrimary.copy(alpha = 0.3f)
                            )
                        )
                    }
                }
            }

            // Device & App System Info
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CyberSurface),
                shape = RoundedCornerShape(12.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Target Device & Build", fontWeight = FontWeight.Bold, fontSize = 14.sp, color = CyberText)
                    Divider(color = CyberBorder, thickness = 0.5.dp)

                    InfoRow("Device Model", "${Build.MANUFACTURER.replaceFirstChar { it.uppercase() }} ${Build.MODEL}")
                    InfoRow("Android Version", "Android ${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT})")
                    InfoRow("App Name", "Overwatch Mobile")
                    InfoRow("Version", "v1.1 (Build 2) - Auto-Updating")
                    InfoRow("Target Architecture", Build.SUPPORTED_ABIS.firstOrNull() ?: "arm64-v8a")
                }
            }
        }
    }
}

@Composable
fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, fontSize = 12.sp, color = CyberTextMuted)
        Text(value, fontSize = 12.sp, color = CyberText, fontFamily = FontFamily.Monospace)
    }
}
