package com.example.overwatch.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.overwatch.model.ServerItem
import com.example.overwatch.model.ServerType
import com.example.overwatch.service.PreferencesManager
import com.example.overwatch.service.ServerProbeService
import com.example.overwatch.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ServerStatusScreen(
    prefs: PreferencesManager,
    probeService: ServerProbeService,
    onNavigateToSsh: (String) -> Unit
) {
    val coroutineScope = rememberCoroutineScope()
    val defaultHost = prefs.defaultHost

    // Initial default core servers
    val defaultServers = remember(defaultHost) {
        listOf(
            ServerItem("core-ftp", "FTP Server", defaultHost, 21, ServerType.FTP),
            ServerItem("core-ruby", "Ruby (Puma/Rack)", defaultHost, 3000, ServerType.RUBY, "/"),
            ServerItem("core-react", "React Web App", defaultHost, 80, ServerType.REACT, "/"),
            ServerItem("core-python", "Python Backend (FastAPI)", defaultHost, 8080, ServerType.PYTHON, "/api/system/status"),
            ServerItem("core-jsproject", "JsProject AI Platform", defaultHost, 8000, ServerType.PYTHON, "/JsProject/")
        )
    }

    var serverList by remember {
        mutableStateOf(defaultServers + prefs.getCustomServers())
    }
    var isCheckingAll by remember { mutableStateOf(false) }
    var showAddDialog by remember { mutableStateOf(false) }

    fun refreshAll() {
        if (isCheckingAll) return
        isCheckingAll = true
        coroutineScope.launch {
            val updated = serverList.map { server ->
                probeService.probeServer(server)
            }
            serverList = updated
            isCheckingAll = false
        }
    }

    // Auto-check on first launch & optional periodic auto-refresh
    LaunchedEffect(Unit) {
        refreshAll()
        while (prefs.autoRefresh) {
            delay(prefs.refreshIntervalSeconds * 1000L)
            refreshAll()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            "Mission Control",
                            fontWeight = FontWeight.Bold,
                            color = CyberText,
                            fontSize = 18.sp
                        )
                        Text(
                            "Host: $defaultHost",
                            color = CyberPrimary,
                            fontSize = 12.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { refreshAll() }, enabled = !isCheckingAll) {
                        if (isCheckingAll) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                color = CyberPrimary,
                                strokeWidth = 2.dp
                            )
                        } else {
                            Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = CyberPrimary)
                        }
                    }
                    IconButton(onClick = { showAddDialog = true }) {
                        Icon(Icons.Default.Add, contentDescription = "Add Server", tint = CyberSecondary)
                    }
                },
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
        ) {
            // Overall Stats Header Card
            val onlineCount = serverList.count { it.isOnline }
            val totalCount = serverList.size

            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                colors = CardDefaults.cardColors(containerColor = CyberSurfaceCard),
                shape = RoundedCornerShape(12.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(10.dp)
                                    .clip(CircleShape)
                                    .background(if (onlineCount > 0) CyberSecondary else CyberError)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                if (onlineCount == totalCount) "ALL SYSTEMS OPERATIONAL" else "$onlineCount OF $totalCount ACTIVE",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (onlineCount > 0) CyberSecondary else CyberError
                            )
                        }
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "Real-time TCP / HTTP Active Probes",
                            fontSize = 11.sp,
                            color = CyberTextMuted
                        )
                    }

                    Button(
                        onClick = { refreshAll() },
                        enabled = !isCheckingAll,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = CyberPrimary.copy(alpha = 0.15f),
                            contentColor = CyberPrimary
                        ),
                        shape = RoundedCornerShape(8.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)
                    ) {
                        Text("Ping All", fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }

            // Server List
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(serverList, key = { it.id }) { server ->
                    ServerStatusCard(
                        server = server,
                        onPingSingle = {
                            coroutineScope.launch {
                                val res = probeService.probeServer(server)
                                serverList = serverList.map { if (it.id == server.id) res else it }
                            }
                        },
                        onDelete = {
                            val custom = prefs.getCustomServers().filter { it.id != server.id }
                            prefs.saveCustomServers(custom)
                            serverList = defaultServers + custom
                        },
                        isCustom = !server.id.startsWith("core-")
                    )
                }
            }
        }
    }

    if (showAddDialog) {
        AddServerDialog(
            defaultHost = defaultHost,
            onDismiss = { showAddDialog = false },
            onAdd = { newServer ->
                val custom = prefs.getCustomServers() + newServer
                prefs.saveCustomServers(custom)
                serverList = defaultServers + custom
                showAddDialog = false
                refreshAll()
            }
        )
    }
}

@Composable
fun ServerStatusCard(
    server: ServerItem,
    onPingSingle: () -> Unit,
    onDelete: () -> Unit,
    isCustom: Boolean
) {
    var expanded by remember { mutableStateOf(false) }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { expanded = !expanded },
        colors = CardDefaults.cardColors(containerColor = CyberSurface),
        shape = RoundedCornerShape(12.dp),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            if (server.isOnline) CyberSecondary.copy(alpha = 0.5f) else CyberBorder
        )
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    // Type Badge Icon
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(
                                when (server.type) {
                                    ServerType.FTP -> CyberAccent.copy(alpha = 0.2f)
                                    ServerType.RUBY -> CyberWarning.copy(alpha = 0.2f)
                                    ServerType.REACT -> CyberPrimary.copy(alpha = 0.2f)
                                    ServerType.PYTHON -> CyberSecondary.copy(alpha = 0.2f)
                                    else -> CyberBorder
                                }
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            when (server.type) {
                                ServerType.FTP -> "FTP"
                                ServerType.RUBY -> "RB"
                                ServerType.REACT -> "RT"
                                ServerType.PYTHON -> "PY"
                                else -> "SRV"
                            },
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = when (server.type) {
                                ServerType.FTP -> CyberAccent
                                ServerType.RUBY -> CyberWarning
                                ServerType.REACT -> CyberPrimary
                                ServerType.PYTHON -> CyberSecondary
                                else -> CyberText
                            }
                        )
                    }

                    Spacer(modifier = Modifier.width(12.dp))

                    Column {
                        Text(
                            server.name,
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 15.sp,
                            color = CyberText
                        )
                        Text(
                            "${server.host}:${server.port}${server.checkPath}",
                            fontSize = 12.sp,
                            color = CyberTextMuted,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }

                // Active Status Badge
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(
                                if (server.isOnline) CyberSecondary.copy(alpha = 0.15f)
                                else CyberError.copy(alpha = 0.15f)
                            )
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(6.dp)
                                    .clip(CircleShape)
                                    .background(if (server.isOnline) CyberSecondary else CyberError)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                if (server.isOnline) "${server.latencyMs}ms" else "OFFLINE",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (server.isOnline) CyberSecondary else CyberError,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }
                }
            }

            AnimatedVisibility(visible = expanded) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 12.dp)
                ) {
                    Divider(color = CyberBorder, thickness = 0.5.dp)
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "Status: ${server.statusMessage}",
                        fontSize = 12.sp,
                        color = if (server.isOnline) CyberSecondary else CyberError
                    )
                    if (server.details.isNotBlank()) {
                        Text(
                            server.details,
                            fontSize = 11.sp,
                            color = CyberTextMuted,
                            fontFamily = FontFamily.Monospace,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 8.dp),
                        horizontalArrangement = Arrangement.End
                    ) {
                        if (isCustom) {
                            TextButton(
                                onClick = onDelete,
                                colors = ButtonDefaults.textButtonColors(contentColor = CyberError)
                            ) {
                                Text("Delete", fontSize = 12.sp)
                            }
                        }
                        TextButton(
                            onClick = onPingSingle,
                            colors = ButtonDefaults.textButtonColors(contentColor = CyberPrimary)
                        ) {
                            Text("Re-test", fontSize = 12.sp)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun AddServerDialog(
    defaultHost: String,
    onDismiss: () -> Unit,
    onAdd: (ServerItem) -> Unit
) {
    var name by remember { mutableStateOf("") }
    var host by remember { mutableStateOf(defaultHost) }
    var portStr by remember { mutableStateOf("8080") }
    var selectedType by remember { mutableStateOf(ServerType.HTTP) }
    var checkPath by remember { mutableStateOf("/") }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = CyberSurface,
        title = { Text("Add Server Monitor", color = CyberText, fontWeight = FontWeight.Bold) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Server Name") },
                    placeholder = { Text("e.g. Node API") },
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = CyberText,
                        unfocusedTextColor = CyberText,
                        focusedBorderColor = CyberPrimary,
                        unfocusedBorderColor = CyberBorder
                    )
                )

                OutlinedTextField(
                    value = host,
                    onValueChange = { host = it },
                    label = { Text("Host / IP") },
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = CyberText,
                        unfocusedTextColor = CyberText,
                        focusedBorderColor = CyberPrimary,
                        unfocusedBorderColor = CyberBorder
                    )
                )

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = portStr,
                        onValueChange = { portStr = it },
                        label = { Text("Port") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = CyberText,
                            unfocusedTextColor = CyberText,
                            focusedBorderColor = CyberPrimary,
                            unfocusedBorderColor = CyberBorder
                        )
                    )

                    OutlinedTextField(
                        value = checkPath,
                        onValueChange = { checkPath = it },
                        label = { Text("Path") },
                        singleLine = true,
                        modifier = Modifier.weight(1.5f),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = CyberText,
                            unfocusedTextColor = CyberText,
                            focusedBorderColor = CyberPrimary,
                            unfocusedBorderColor = CyberBorder
                        )
                    )
                }

                Text("Protocol Type:", fontSize = 12.sp, color = CyberTextMuted)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf(ServerType.HTTP, ServerType.TCP, ServerType.FTP).forEach { type ->
                        FilterChip(
                            selected = selectedType == type,
                            onClick = { selectedType = type },
                            label = { Text(type.name, fontSize = 11.sp) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = CyberPrimary.copy(alpha = 0.2f),
                                selectedLabelColor = CyberPrimary
                            )
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val port = portStr.toIntOrNull() ?: 80
                    if (name.isNotBlank() && host.isNotBlank()) {
                        onAdd(
                            ServerItem(
                                id = "custom-${System.currentTimeMillis()}",
                                name = name.trim(),
                                host = host.trim(),
                                port = port,
                                type = selectedType,
                                checkPath = checkPath.trim()
                            )
                        )
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = CyberPrimary, contentColor = CyberBg)
            ) {
                Text("Add Probe")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, colors = ButtonDefaults.textButtonColors(contentColor = CyberTextMuted)) {
                Text("Cancel")
            }
        }
    )
}
