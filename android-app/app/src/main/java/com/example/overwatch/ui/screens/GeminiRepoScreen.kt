package com.example.overwatch.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.automirrored.filled.*
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
import com.example.overwatch.model.ChatMessage
import com.example.overwatch.model.GitHubRepo
import com.example.overwatch.model.MessageSender
import com.example.overwatch.service.AnalysisMode
import com.example.overwatch.service.GeminiService
import com.example.overwatch.service.GitHubService
import com.example.overwatch.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GeminiRepoScreen(
    gitHubService: GitHubService,
    geminiService: GeminiService
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    var repos by remember { mutableStateOf<List<GitHubRepo>>(emptyList()) }
    var isLoadingRepos by remember { mutableStateOf(false) }
    var searchQuery by remember { mutableStateOf("") }
    var selectedRepo by remember { mutableStateOf<GitHubRepo?>(null) }

    // Gemini Chat & Analysis State
    var readmeContent by remember { mutableStateOf("") }
    var fileList by remember { mutableStateOf<List<String>>(emptyList()) }
    var isAnalyzing by remember { mutableStateOf(false) }
    var chatMessages by remember { mutableStateOf<List<ChatMessage>>(emptyList()) }
    var currentPrompt by remember { mutableStateOf("") }

    fun loadRepos() {
        isLoadingRepos = true
        coroutineScope.launch {
            try {
                repos = gitHubService.fetchRepositories("therealbonz")
            } catch (e: Exception) {
                // Fallback default sample repos if network error
                repos = listOf(
                    GitHubRepo(1, "Overwatch", "therealbonz/Overwatch", "Central Project Launchpad & CMS", "Python", 4, 1, false, "https://github.com/therealbonz/Overwatch", "https://github.com/therealbonz/Overwatch.git", "Just now"),
                    GitHubRepo(2, "JsProject", "therealbonz/JsProject", "AI Sales Automation & Cold Calling Platform", "JavaScript", 8, 2, false, "https://github.com/therealbonz/JsProject", "https://github.com/therealbonz/JsProject.git", "Yesterday"),
                    GitHubRepo(3, "Bonz2D", "therealbonz/Bonz2D", "Action 2D Unity Adventure Game", "C#", 12, 3, false, "https://github.com/therealbonz/Bonz2D", "https://github.com/therealbonz/Bonz2D.git", "3 days ago")
                )
            } finally {
                isLoadingRepos = false
            }
        }
    }

    LaunchedEffect(Unit) {
        loadRepos()
    }

    // When a repo is selected, fetch its README and file tree
    LaunchedEffect(selectedRepo) {
        val repo = selectedRepo
        if (repo != null) {
            readmeContent = "Loading repository README..."
            fileList = emptyList()
            coroutineScope.launch {
                readmeContent = gitHubService.fetchReadme(repo.fullName)
                fileList = gitHubService.fetchFileTree(repo.fullName)
            }
        }
    }

    fun runAnalysis(mode: AnalysisMode) {
        val repo = selectedRepo ?: return
        isAnalyzing = true
        coroutineScope.launch {
            val userMsg = ChatMessage(sender = MessageSender.USER, text = "Run ${mode.title}")
            chatMessages = chatMessages + userMsg

            val aiResponse = geminiService.analyzeRepository(repo, readmeContent, fileList, mode)
            val geminiMsg = ChatMessage(sender = MessageSender.GEMINI, text = aiResponse)
            chatMessages = chatMessages + geminiMsg
            isAnalyzing = false
        }
    }

    fun sendCustomPrompt(text: String) {
        if (text.isBlank() || isAnalyzing) return
        isAnalyzing = true
        val userMsg = ChatMessage(sender = MessageSender.USER, text = text)
        chatMessages = chatMessages + userMsg
        currentPrompt = ""

        coroutineScope.launch {
            val answer = geminiService.askQuestion(selectedRepo, text, chatMessages)
            val geminiMsg = ChatMessage(sender = MessageSender.GEMINI, text = answer)
            chatMessages = chatMessages + geminiMsg
            isAnalyzing = false
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            if (selectedRepo == null) "Gemini Repo Analyst" else selectedRepo!!.name,
                            fontWeight = FontWeight.Bold,
                            color = CyberText,
                            fontSize = 18.sp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(CyberAccent.copy(alpha = 0.2f))
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text("Gemini 2.0", fontSize = 10.sp, color = CyberAccent, fontWeight = FontWeight.Bold)
                        }
                    }
                },
                navigationIcon = {
                    if (selectedRepo != null) {
                        IconButton(onClick = { selectedRepo = null }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = CyberPrimary)
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { loadRepos() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh Repos", tint = CyberPrimary)
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
            if (selectedRepo == null) {
                // Repository Selection View
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it },
                    placeholder = { Text("Search repositories...", color = CyberTextMuted) },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = "Search", tint = CyberPrimary) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = CyberText,
                        unfocusedTextColor = CyberText,
                        focusedBorderColor = CyberPrimary,
                        unfocusedBorderColor = CyberBorder
                    )
                )

                val filteredRepos = repos.filter {
                    it.name.contains(searchQuery, ignoreCase = true) ||
                            it.description.contains(searchQuery, ignoreCase = true) ||
                            it.language.contains(searchQuery, ignoreCase = true)
                }

                if (isLoadingRepos && repos.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = CyberPrimary)
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(filteredRepos, key = { it.id }) { repo ->
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { selectedRepo = repo },
                                colors = CardDefaults.cardColors(containerColor = CyberSurface),
                                shape = RoundedCornerShape(12.dp),
                                border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
                            ) {
                                Column(modifier = Modifier.padding(14.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            repo.name,
                                            fontWeight = FontWeight.Bold,
                                            fontSize = 16.sp,
                                            color = CyberPrimary
                                        )

                                        Box(
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(6.dp))
                                                .background(CyberSurfaceCard)
                                                .padding(horizontal = 8.dp, vertical = 3.dp)
                                        ) {
                                            Text(
                                                repo.language,
                                                fontSize = 11.sp,
                                                color = CyberTextMuted,
                                                fontWeight = FontWeight.SemiBold
                                            )
                                        }
                                    }

                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        repo.description,
                                        fontSize = 12.sp,
                                        color = CyberTextMuted,
                                        maxLines = 2
                                    )

                                    Spacer(modifier = Modifier.height(10.dp))
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                                    ) {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Icon(Icons.Default.Star, contentDescription = "Stars", tint = CyberWarning, modifier = Modifier.size(14.dp))
                                            Spacer(modifier = Modifier.width(4.dp))
                                            Text("${repo.stars}", fontSize = 11.sp, color = CyberTextMuted)
                                        }

                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Icon(Icons.Default.Share, contentDescription = "Forks", tint = CyberPrimary, modifier = Modifier.size(14.dp))
                                            Spacer(modifier = Modifier.width(4.dp))
                                            Text("${repo.forks}", fontSize = 11.sp, color = CyberTextMuted)
                                        }

                                        Text("Tap to examine with Gemini", fontSize = 11.sp, color = CyberAccent, fontWeight = FontWeight.Medium)
                                    }
                                }
                            }
                        }
                    }
                }

            } else {
                // Active Gemini Repository Inspection View
                val currentRepo = selectedRepo!!

                LazyColumn(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f)
                        .padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    item {
                        Card(
                            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                            colors = CardDefaults.cardColors(containerColor = CyberSurfaceCard),
                            shape = RoundedCornerShape(12.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, CyberBorder)
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(currentRepo.fullName, fontWeight = FontWeight.Bold, color = CyberText, fontSize = 14.sp)
                                    IconButton(
                                        onClick = {
                                            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                            clipboard.setPrimaryClip(ClipData.newPlainText("Clone URL", currentRepo.cloneUrl))
                                            Toast.makeText(context, "Copied clone URL!", Toast.LENGTH_SHORT).show()
                                        },
                                        modifier = Modifier.size(24.dp)
                                    ) {
                                        Icon(Icons.Default.ContentCopy, contentDescription = "Copy Clone URL", tint = CyberPrimary, modifier = Modifier.size(16.dp))
                                    }
                                }
                                Text(currentRepo.description, fontSize = 12.sp, color = CyberTextMuted)
                            }
                        }
                    }

                    // Prompt Preset Chips
                    item {
                        Text("Gemini Analysis Actions:", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = CyberTextMuted)
                        Spacer(modifier = Modifier.height(4.dp))
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(AnalysisMode.values()) { mode ->
                                ActionChip(
                                    label = when (mode) {
                                        AnalysisMode.ARCHITECTURE -> "⚡ Architecture"
                                        AnalysisMode.SECURITY_AUDIT -> "🛡️ Security"
                                        AnalysisMode.REFACTOR_IDEAS -> "💡 Proposals"
                                        AnalysisMode.QUICK_SUMMARY -> "📄 Summary"
                                    },
                                    onClick = { runAnalysis(mode) },
                                    enabled = !isAnalyzing
                                )
                            }
                        }
                    }

                    // Chat / Analysis Messages
                    if (chatMessages.isEmpty() && !isAnalyzing) {
                        item {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 32.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    "Tap an analysis action above or ask Gemini anything about this repo below.",
                                    color = CyberTextMuted,
                                    fontSize = 12.sp,
                                    textAlign = androidx.compose.ui.text.style.TextAlign.Center
                                )
                            }
                        }
                    }

                    items(chatMessages) { message ->
                        ChatMessageBubble(message = message)
                    }

                    if (isAnalyzing) {
                        item {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(8.dp),
                                horizontalArrangement = Arrangement.Center,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                CircularProgressIndicator(modifier = Modifier.size(18.dp), color = CyberAccent, strokeWidth = 2.dp)
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("Gemini is analyzing repository...", fontSize = 12.sp, color = CyberAccent)
                            }
                        }
                    }
                }

                // Chat Input Bar
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(CyberSurface)
                        .padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = currentPrompt,
                        onValueChange = { currentPrompt = it },
                        placeholder = { Text("Ask Gemini about ${currentRepo.name}...", fontSize = 12.sp, color = CyberTextMuted) },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(24.dp),
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
                        onClick = { sendCustomPrompt(currentPrompt) },
                        enabled = currentPrompt.isNotBlank() && !isAnalyzing,
                        modifier = Modifier
                            .size(42.dp)
                            .clip(CircleShape)
                            .background(if (currentPrompt.isNotBlank() && !isAnalyzing) CyberPrimary else CyberBorder)
                    ) {
                        Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send", tint = CyberBg, modifier = Modifier.size(18.dp))
                    }
                }
            }
        }
    }
}

@Composable
fun ActionChip(label: String, onClick: () -> Unit, enabled: Boolean) {
    Surface(
        onClick = onClick,
        enabled = enabled,
        shape = RoundedCornerShape(8.dp),
        color = CyberSurfaceCard,
        border = androidx.compose.foundation.BorderStroke(1.dp, CyberAccent.copy(alpha = 0.5f))
    ) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            fontSize = 12.sp,
            color = CyberText,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
fun ChatMessageBubble(message: ChatMessage) {
    val isUser = message.sender == MessageSender.USER
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        Row(
            modifier = Modifier
                .clip(RoundedCornerShape(12.dp))
                .background(if (isUser) CyberPrimary.copy(alpha = 0.2f) else CyberSurfaceCard)
                .border(
                    1.dp,
                    if (isUser) CyberPrimary.copy(alpha = 0.4f) else CyberBorder,
                    RoundedCornerShape(12.dp)
                )
                .padding(12.dp)
                .widthIn(max = 320.dp)
        ) {
            Column {
                Text(
                    if (isUser) "You" else "Gemini AI",
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (isUser) CyberPrimary else CyberAccent
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    message.text,
                    fontSize = 13.sp,
                    color = CyberText,
                    fontFamily = if (!isUser && (message.text.contains("```") || message.text.contains("- "))) FontFamily.Default else FontFamily.Default
                )
            }
        }
    }
}
