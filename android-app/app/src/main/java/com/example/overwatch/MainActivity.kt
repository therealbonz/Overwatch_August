package com.example.overwatch

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.overwatch.service.*
import com.example.overwatch.theme.*
import androidx.compose.material.icons.filled.ConnectedTv
import com.example.overwatch.ui.screens.AntigravityScreen
import com.example.overwatch.ui.screens.GeminiRepoScreen
import com.example.overwatch.ui.screens.ServerStatusScreen
import com.example.overwatch.ui.screens.SettingsScreen
import com.example.overwatch.ui.screens.SshTerminalScreen

enum class AppTab(val title: String, val icon: ImageVector) {
    SERVERS("Servers", Icons.Default.Dns),
    VNC("Antigravity", Icons.Default.ConnectedTv),
    REPOS("Gemini Repos", Icons.Default.AutoAwesome),
    SSH("SSH Plugin", Icons.Default.Terminal),
    SETTINGS("Settings", Icons.Default.Settings)
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setShowWhenLocked(true)
        setTurnScreenOn(true)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        enableEdgeToEdge()

        setContent {
            OverwatchTheme {
                val context = LocalContext.current
                val prefs = remember { PreferencesManager(context) }
                val probeService = remember { ServerProbeService() }
                val gitHubService = remember { GitHubService() }
                val geminiService = remember { GeminiService(prefs) }
                val sshService = remember { SshService() }
                val updateService = remember { AutoUpdateService(context) }

                var selectedTab by remember { mutableStateOf(AppTab.VNC) }

                // Auto-update check on app launch
                LaunchedEffect(Unit) {
                    if (prefs.autoUpdateOnLaunch) {
                        val u = updateService.checkUpdate(prefs.vncBridgeHost)
                        if (u != null) {
                            updateService.downloadAndInstall(
                                downloadUrl = u.downloadUrl,
                                onProgress = {},
                                onError = {}
                            )
                        }
                    }
                }

                Scaffold(
                    bottomBar = {
                        NavigationBar(
                            containerColor = CyberSurface,
                            tonalElevation = 8.dp
                        ) {
                            AppTab.values().forEach { tab ->
                                val selected = selectedTab == tab
                                NavigationBarItem(
                                    selected = selected,
                                    onClick = { selectedTab = tab },
                                    icon = {
                                        Icon(
                                            tab.icon,
                                            contentDescription = tab.title,
                                            tint = if (selected) CyberPrimary else CyberTextMuted
                                        )
                                    },
                                    label = {
                                        Text(
                                            tab.title,
                                            fontSize = 11.sp,
                                            color = if (selected) CyberPrimary else CyberTextMuted
                                        )
                                    },
                                    colors = NavigationBarItemDefaults.colors(
                                        indicatorColor = CyberPrimary.copy(alpha = 0.15f)
                                    )
                                )
                            }
                        }
                    },
                    containerColor = CyberBg
                ) { innerPadding ->
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(innerPadding)
                    ) {
                        when (selectedTab) {
                            AppTab.VNC -> AntigravityScreen(
                                prefs = prefs,
                                updateService = updateService
                            )
                            AppTab.SERVERS -> ServerStatusScreen(
                                prefs = prefs,
                                probeService = probeService,
                                onNavigateToSsh = { selectedTab = AppTab.SSH }
                            )
                            AppTab.REPOS -> GeminiRepoScreen(
                                gitHubService = gitHubService,
                                geminiService = geminiService
                            )
                            AppTab.SSH -> SshTerminalScreen(
                                prefs = prefs,
                                sshService = sshService
                            )
                            AppTab.SETTINGS -> SettingsScreen(
                                prefs = prefs,
                                geminiService = geminiService
                            )
                        }
                    }
                }
            }
        }
    }
}
