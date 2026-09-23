package com.example.overwatch.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.overwatch.model.SshProfile
import com.example.overwatch.service.PreferencesManager
import com.example.overwatch.service.SshService
import com.example.overwatch.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SshTerminalScreen(
    prefs: PreferencesManager,
    sshService: SshService
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    val listState = rememberLazyListState()

    var profiles by remember { mutableStateOf(prefs.getSshProfiles()) }
    var selectedProfile by remember { mutableStateOf(profiles.firstOrNull() ?: SshProfile(name = "Default", host = prefs.defaultHost)) }

    var terminalLines by remember {
        mutableStateOf(
            listOf(
                "⚡ Overwatch Remote SSH Terminal",
                "Connected target: ${selectedProfile.username}@${selectedProfile.host}:${selectedProfile.port}",
                "Type a shell command or tap 'Add Thing' to deploy services & repos."
            )
        )
    }

    var commandInput by remember { mutableStateOf("") }
    var isExecuting by remember { mutableStateOf(false) }
    var showAddThingDialog by remember { mutableStateOf(false) }
    var showEditProfileDialog by remember { mutableStateOf(false) }

    fun appendLine(line: String) {
        terminalLines = terminalLines + line
    }

    fun runCommand(cmd: String) {
        if (cmd.isBlank() || isExecuting) return
        val commandToRun = cmd.trim()
        commandInput = ""
        isExecuting = true

        coroutineScope.launch {
            sshService.executeCommand(
                profile = selectedProfile,
                command = commandToRun,
                onOutput = { line ->
                    appendLine(line)
                }
            )
            isExecuting = false
            listState.animateScrollToItem((terminalLines.size - 1).coerceAtLeast(0))
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("SSH Control & Plugin", fontWeight = FontWeight.Bold, color = CyberText, fontSize = 17.sp)
                        Text(
                            "${selectedProfile.username}@${selectedProfile.host}",
                            fontSize = 12.sp,
                            color = CyberPrimary,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { showEditProfileDialog = true }) {
                        Icon(Icons.Default.Key, contentDescription = "SSH Credentials", tint = CyberPrimary)
                    }
                    IconButton(onClick = { showAddThingDialog = true }) {
                        Icon(Icons.Default.AddCircle, contentDescription = "Add Thing", tint = CyberSecondary)
                    }
                    IconButton(onClick = {
                        val text = terminalLines.joinToString("\n")
                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        clipboard.setPrimaryClip(ClipData.newPlainText("Terminal Logs", text))
                        Toast.makeText(context, "Copied terminal output", Toast.LENGTH_SHORT).show()
                    }) {
                        Icon(Icons.Default.ContentCopy, contentDescription = "Copy Output", tint = CyberTextMuted)
                    }
                    IconButton(onClick = { terminalLines = emptyList() }) {
                        Icon(Icons.Default.ClearAll, contentDescription = "Clear", tint = CyberTextMuted)
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
            // Quick Action & Shortcut Chips
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(CyberSurfaceCard)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                item {
                    Button(
                        onClick = { showAddThingDialog = true },
                        colors = ButtonDefaults.buttonColors(containerColor = CyberSecondary, contentColor = CyberBg),
                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("+ Add Thing", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    }
                }

                val quickCommands = listOf(
                    "status" to "systemctl status therealbonz-homepage --no-pager",
                    "restart" to "sudo systemctl restart therealbonz-homepage",
                    "disk" to "df -h /",
                    "mem" to "free -m",
                    "logs" to "journalctl -u therealbonz-homepage -n 15 --no-pager",
                    "git pull" to "cd /var/www/therealbonz && git pull",
                    "ps" to "ps aux | grep -E 'python|ruby|react|nginx' | head -n 15"
                )

                items(quickCommands) { (label, cmd) ->
                    AssistChip(
                        onClick = { runCommand(cmd) },
                        label = { Text(label, fontSize = 11.sp, fontFamily = FontFamily.Monospace) },
                        colors = AssistChipDefaults.assistChipColors(
                            containerColor = CyberSurface,
                            labelColor = CyberPrimary
                        ),
                        border = AssistChipDefaults.assistChipBorder(borderColor = CyberBorder, enabled = true)
                    )
                }
            }

            // Monospace Terminal Output View
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .background(CyberTerminalBg)
                    .padding(8.dp)
            ) {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(2.dp)
                ) {
                    items(terminalLines) { line ->
                        Text(
                            text = line,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp,
                            color = when {
                                line.startsWith("❌") || line.startsWith("⚠️") -> CyberError
                                line.startsWith("✅") -> CyberSecondary
                                line.startsWith("🔌") || line.startsWith("⚡") -> CyberPrimary
                                line.startsWith("$") -> CyberAccent
                                else -> CyberText
                            },
                            lineHeight = 15.sp
                        )
                    }
                }

                if (isExecuting) {
                    Box(
                        modifier = Modifier
                            .align(Alignment.TopEnd)
                            .padding(8.dp)
                            .clip(RoundedCornerShape(6.dp))
                            .background(CyberSurfaceCard)
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(modifier = Modifier.size(12.dp), color = CyberPrimary, strokeWidth = 2.dp)
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("RUNNING", fontSize = 10.sp, color = CyberPrimary, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            // Command Input Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(CyberSurface)
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("$", fontFamily = FontFamily.Monospace, fontSize = 16.sp, color = CyberPrimary, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.width(8.dp))

                OutlinedTextField(
                    value = commandInput,
                    onValueChange = { commandInput = it },
                    placeholder = { Text("Enter command...", fontSize = 12.sp, color = CyberTextMuted, fontFamily = FontFamily.Monospace) },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = CyberText,
                        unfocusedTextColor = CyberText,
                        focusedBorderColor = CyberPrimary,
                        unfocusedBorderColor = CyberBorder
                    ),
                    singleLine = true
                )

                Spacer(modifier = Modifier.width(8.dp))

                IconButton(
                    onClick = { runCommand(commandInput) },
                    enabled = commandInput.isNotBlank() && !isExecuting,
                    modifier = Modifier
                        .size(42.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (commandInput.isNotBlank() && !isExecuting) CyberPrimary else CyberBorder)
                ) {
                    Icon(Icons.Default.PlayArrow, contentDescription = "Execute", tint = CyberBg)
                }
            }
        }
    }

    // "Add Thing" Dialog Wizard
    if (showAddThingDialog) {
        AddThingDialog(
            onDismiss = { showAddThingDialog = false },
            onCloneRepo = { url, dest ->
                showAddThingDialog = false
                isExecuting = true
                coroutineScope.launch {
                    sshService.cloneRepository(selectedProfile, url, dest) { appendLine(it) }
                    isExecuting = false
                }
            },
            onAddService = { name, cmd ->
                showAddThingDialog = false
                isExecuting = true
                coroutineScope.launch {
                    sshService.addService(selectedProfile, name, cmd) { appendLine(it) }
                    isExecuting = false
                }
            },
            onCreateFolder = { folderName ->
                showAddThingDialog = false
                isExecuting = true
                coroutineScope.launch {
                    sshService.createDirectory(selectedProfile, folderName) { appendLine(it) }
                    isExecuting = false
                }
            }
        )
    }

    // Edit Profile / Credentials Dialog
    if (showEditProfileDialog) {
        EditSshProfileDialog(
            currentProfile = selectedProfile,
            onDismiss = { showEditProfileDialog = false },
            onSave = { updated ->
                selectedProfile = updated
                val list = profiles.map { if (it.id == updated.id) updated else it }
                profiles = list
                prefs.saveSshProfiles(list)
                showEditProfileDialog = false
                Toast.makeText(context, "SSH Profile updated", Toast.LENGTH_SHORT).show()
            }
        )
    }
}

@Composable
fun AddThingDialog(
    onDismiss: () -> Unit,
    onCloneRepo: (url: String, dest: String) -> Unit,
    onAddService: (name: String, cmd: String) -> Unit,
    onCreateFolder: (name: String) -> Unit
) {
    var selectedTab by remember { mutableStateOf(0) } // 0: Clone Repo, 1: Add Service, 2: Add Folder

    var repoUrl by remember { mutableStateOf("") }
    var destFolder by remember { mutableStateOf("") }

    var serviceName by remember { mutableStateOf("") }
    var serviceCmd by remember { mutableStateOf("") }

    var folderName by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = CyberSurface,
        title = { Text("SSH Plugin: Add Thing", color = CyberText, fontWeight = FontWeight.Bold) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                TabRow(
                    selectedTabIndex = selectedTab,
                    containerColor = CyberSurfaceCard,
                    contentColor = CyberPrimary
                ) {
                    Tab(selected = selectedTab == 0, onClick = { selectedTab = 0 }) {
                        Text("Git Repo", fontSize = 12.sp, modifier = Modifier.padding(vertical = 8.dp))
                    }
                    Tab(selected = selectedTab == 1, onClick = { selectedTab = 1 }) {
                        Text("Service", fontSize = 12.sp, modifier = Modifier.padding(vertical = 8.dp))
                    }
                    Tab(selected = selectedTab == 2, onClick = { selectedTab = 2 }) {
                        Text("Folder", fontSize = 12.sp, modifier = Modifier.padding(vertical = 8.dp))
                    }
                }

                when (selectedTab) {
                    0 -> {
                        OutlinedTextField(
                            value = repoUrl,
                            onValueChange = { repoUrl = it },
                            label = { Text("Repository Git URL") },
                            placeholder = { Text("https://github.com/therealbonz/...") },
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(focusedTextColor = CyberText, unfocusedTextColor = CyberText)
                        )
                        OutlinedTextField(
                            value = destFolder,
                            onValueChange = { destFolder = it },
                            label = { Text("Target Directory (Optional)") },
                            placeholder = { Text("defaults to repo name") },
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(focusedTextColor = CyberText, unfocusedTextColor = CyberText)
                        )
                    }
                    1 -> {
                        OutlinedTextField(
                            value = serviceName,
                            onValueChange = { serviceName = it },
                            label = { Text("Service Name") },
                            placeholder = { Text("e.g. ruby-api or react-node") },
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(focusedTextColor = CyberText, unfocusedTextColor = CyberText)
                        )
                        OutlinedTextField(
                            value = serviceCmd,
                            onValueChange = { serviceCmd = it },
                            label = { Text("Execution Command") },
                            placeholder = { Text("python3 -m uvicorn ...") },
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(focusedTextColor = CyberText, unfocusedTextColor = CyberText)
                        )
                    }
                    2 -> {
                        OutlinedTextField(
                            value = folderName,
                            onValueChange = { folderName = it },
                            label = { Text("Directory Name") },
                            placeholder = { Text("e.g. my-new-site") },
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(focusedTextColor = CyberText, unfocusedTextColor = CyberText)
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    when (selectedTab) {
                        0 -> if (repoUrl.isNotBlank()) onCloneRepo(repoUrl, destFolder)
                        1 -> if (serviceName.isNotBlank() && serviceCmd.isNotBlank()) onAddService(serviceName, serviceCmd)
                        2 -> if (folderName.isNotBlank()) onCreateFolder(folderName)
                    }
                },
                colors = ButtonDefaults.buttonColors(containerColor = CyberSecondary, contentColor = CyberBg)
            ) {
                Text("Deploy via SSH")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, colors = ButtonDefaults.textButtonColors(contentColor = CyberTextMuted)) {
                Text("Cancel")
            }
        }
    )
}

@Composable
fun EditSshProfileDialog(
    currentProfile: SshProfile,
    onDismiss: () -> Unit,
    onSave: (SshProfile) -> Unit
) {
    var host by remember { mutableStateOf(currentProfile.host) }
    var portStr by remember { mutableStateOf(currentProfile.port.toString()) }
    var username by remember { mutableStateOf(currentProfile.username) }
    var password by remember { mutableStateOf(currentProfile.password) }
    var privateKey by remember { mutableStateOf(currentProfile.privateKey) }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = CyberSurface,
        title = { Text("SSH Host & Credentials", color = CyberText, fontWeight = FontWeight.Bold) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(
                    value = host,
                    onValueChange = { host = it },
                    label = { Text("Host") },
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = CyberText, unfocusedTextColor = CyberText)
                )

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = username,
                        onValueChange = { username = it },
                        label = { Text("User") },
                        singleLine = true,
                        modifier = Modifier.weight(1.5f),
                        colors = OutlinedTextFieldDefaults.colors(focusedTextColor = CyberText, unfocusedTextColor = CyberText)
                    )
                    OutlinedTextField(
                        value = portStr,
                        onValueChange = { portStr = it },
                        label = { Text("Port") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                        colors = OutlinedTextFieldDefaults.colors(focusedTextColor = CyberText, unfocusedTextColor = CyberText)
                    )
                }

                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Password (Optional)") },
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = CyberText, unfocusedTextColor = CyberText)
                )

                OutlinedTextField(
                    value = privateKey,
                    onValueChange = { privateKey = it },
                    label = { Text("SSH Private Key PEM (Optional)") },
                    placeholder = { Text("-----BEGIN OPENSSH PRIVATE KEY-----") },
                    maxLines = 4,
                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = CyberText, unfocusedTextColor = CyberText)
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSave(
                        currentProfile.copy(
                            host = host.trim(),
                            port = portStr.toIntOrNull() ?: 22,
                            username = username.trim(),
                            password = password,
                            privateKey = privateKey.trim()
                        )
                    )
                },
                colors = ButtonDefaults.buttonColors(containerColor = CyberPrimary, contentColor = CyberBg)
            ) {
                Text("Save Profile")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, colors = ButtonDefaults.textButtonColors(contentColor = CyberTextMuted)) {
                Text("Cancel")
            }
        }
    )
}
