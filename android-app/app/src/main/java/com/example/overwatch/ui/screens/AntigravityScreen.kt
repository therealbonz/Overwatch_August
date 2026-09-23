package com.example.overwatch.ui.screens

import android.annotation.SuppressLint
import android.content.Context
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.example.overwatch.service.AutoUpdateService
import com.example.overwatch.service.PreferencesManager
import com.example.overwatch.service.UpdateInfo
import com.example.overwatch.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun AntigravityScreen(
    prefs: PreferencesManager,
    updateService: AutoUpdateService
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var hostInput by remember { mutableStateOf(prefs.vncBridgeHost) }
    var portInput by remember { mutableStateOf(prefs.vncBridgePort.toString()) }
    var showHostDialog by remember { mutableStateOf(false) }
    var webViewInstance by remember { mutableStateOf<WebView?>(null) }

    var updateInfo by remember { mutableStateOf<UpdateInfo?>(null) }
    var isDownloadingUpdate by remember { mutableStateOf(false) }
    var downloadProgress by remember { mutableFloatStateOf(0f) }

    val currentUrl = remember(prefs.vncBridgeHost, prefs.vncBridgePort) {
        "http://${prefs.vncBridgeHost}:${prefs.vncBridgePort}/"
    }

    // Auto-check for updates if enabled
    LaunchedEffect(Unit) {
        if (prefs.autoUpdateOnLaunch) {
            val u = updateService.checkUpdate(prefs.vncBridgeHost)
            if (u != null) {
                updateInfo = u
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CyberBg)
    ) {
        // Top Toolbar
        Surface(
            color = CyberSurface,
            tonalElevation = 4.dp,
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "ANTIGRAVITY VNC",
                            color = CyberPrimary,
                            fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
                            fontSize = 14.sp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        AssistChip(
                            onClick = {
                                prefs.vncBridgeHost = "127.0.0.1"
                                webViewInstance?.loadUrl("http://127.0.0.1:${prefs.vncBridgePort}/")
                            },
                            label = { Text("USB", fontSize = 11.sp) },
                            colors = AssistChipDefaults.assistChipColors(
                                labelColor = if (prefs.vncBridgeHost == "127.0.0.1") CyberPrimary else CyberTextMuted,
                                containerColor = CyberBg
                            )
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        AssistChip(
                            onClick = {
                                prefs.vncBridgeHost = "10.0.0.189"
                                webViewInstance?.loadUrl("http://10.0.0.189:${prefs.vncBridgePort}/")
                            },
                            label = { Text("Wi-Fi", fontSize = 11.sp) },
                            colors = AssistChipDefaults.assistChipColors(
                                labelColor = if (prefs.vncBridgeHost != "127.0.0.1") CyberPrimary else CyberTextMuted,
                                containerColor = CyberBg
                            )
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        IconButton(onClick = { showHostDialog = true }, modifier = Modifier.size(28.dp)) {
                            Icon(Icons.Default.Settings, contentDescription = "Edit Host", tint = CyberTextMuted, modifier = Modifier.size(16.dp))
                        }
                    }

                    Row {
                        IconButton(onClick = {
                            scope.launch(Dispatchers.IO) {
                                try {
                                    val req = Request.Builder()
                                        .url("http://${prefs.vncBridgeHost}:${prefs.vncBridgePort}/api/focus")
                                        .post(okhttp3.RequestBody.create(null, ByteArray(0)))
                                        .build()
                                    OkHttpClient().newCall(req).execute()
                                    withContext(Dispatchers.Main) {
                                        Toast.makeText(context, "Antigravity focused on PC", Toast.LENGTH_SHORT).show()
                                    }
                                } catch (e: Exception) {
                                    withContext(Dispatchers.Main) {
                                        Toast.makeText(context, "Focus failed: ${e.message}", Toast.LENGTH_SHORT).show()
                                    }
                                }
                            }
                        }) {
                            Icon(Icons.Default.FitScreen, contentDescription = "Focus PC Window", tint = CyberPrimary)
                        }

                        IconButton(onClick = {
                            webViewInstance?.reload()
                        }) {
                            Icon(Icons.Default.Refresh, contentDescription = "Reload Viewport", tint = CyberText)
                        }

                        IconButton(onClick = {
                            scope.launch {
                                val u = updateService.checkUpdate(prefs.vncBridgeHost)
                                if (u != null) {
                                    updateInfo = u
                                } else {
                                    Toast.makeText(context, "App is up to date (v${updateService.getCurrentVersionName()})", Toast.LENGTH_SHORT).show()
                                }
                            }
                        }) {
                            Icon(Icons.Default.SystemUpdate, contentDescription = "Check Update", tint = CyberAccent)
                        }
                    }
                }

                // Update notification bar if update is available
                if (updateInfo != null) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Card(
                        colors = CardDefaults.cardColors(containerColor = CyberPrimary.copy(alpha = 0.15f)),
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "Update Available: v${updateInfo?.versionName}",
                                    color = CyberPrimary,
                                    fontSize = 12.sp,
                                    fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
                                )
                                Text(
                                    text = updateInfo?.changelog ?: "New enhancements ready",
                                    color = CyberTextMuted,
                                    fontSize = 10.sp
                                )
                                if (isDownloadingUpdate) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    LinearProgressIndicator(
                                        progress = { downloadProgress },
                                        modifier = Modifier.fillMaxWidth(),
                                        color = CyberPrimary
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.width(8.dp))
                            Button(
                                onClick = {
                                    val dl = updateInfo?.downloadUrl ?: return@Button
                                    isDownloadingUpdate = true
                                    scope.launch {
                                        updateService.downloadAndInstall(
                                            downloadUrl = dl,
                                            onProgress = { downloadProgress = it },
                                            onError = { err ->
                                                isDownloadingUpdate = false
                                                Toast.makeText(context, err, Toast.LENGTH_LONG).show()
                                            }
                                        )
                                    }
                                },
                                enabled = !isDownloadingUpdate,
                                colors = ButtonDefaults.buttonColors(containerColor = CyberPrimary),
                                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp)
                            ) {
                                Text(
                                    text = if (isDownloadingUpdate) "Downloading..." else "Install",
                                    color = Color.Black,
                                    fontSize = 11.sp,
                                    fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
                                )
                            }
                        }
                    }
                }
            }
        }

        // Main WebView Display
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
        ) {
            AndroidView(
                factory = { ctx ->
                    WebView(ctx).apply {
                        layoutParams = ViewGroup.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT
                        )
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        settings.loadWithOverviewMode = true
                        settings.useWideViewPort = true
                        settings.setSupportZoom(true)
                        settings.builtInZoomControls = true
                        settings.displayZoomControls = false

                        webViewClient = object : WebViewClient() {}
                        webChromeClient = WebChromeClient()

                        loadUrl(currentUrl)
                        webViewInstance = this
                    }
                },
                update = { webView ->
                    if (webView.url != currentUrl) {
                        webView.loadUrl(currentUrl)
                    }
                },
                modifier = Modifier.fillMaxSize()
            )
        }
    }

    // Host & Port Configuration Dialog
    if (showHostDialog) {
        AlertDialog(
            onDismissRequest = { showHostDialog = false },
            title = { Text("Configure VNC Bridge Host", color = CyberText) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = hostInput,
                        onValueChange = { hostInput = it },
                        label = { Text("PC / Host IP") },
                        singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = CyberPrimary,
                            unfocusedBorderColor = CyberBorder
                        )
                    )
                    OutlinedTextField(
                        value = portInput,
                        onValueChange = { portInput = it },
                        label = { Text("Web Port (Default 5901)") },
                        singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = CyberPrimary,
                            unfocusedBorderColor = CyberBorder
                        )
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    prefs.vncBridgeHost = hostInput.trim()
                    prefs.vncBridgePort = portInput.toIntOrNull() ?: 5901
                    showHostDialog = false
                    webViewInstance?.loadUrl("http://${prefs.vncBridgeHost}:${prefs.vncBridgePort}/")
                }) {
                    Text("Save & Connect", color = CyberPrimary)
                }
            },
            dismissButton = {
                TextButton(onClick = { showHostDialog = false }) {
                    Text("Cancel", color = CyberTextMuted)
                }
            },
            containerColor = CyberSurface
        )
    }
}
