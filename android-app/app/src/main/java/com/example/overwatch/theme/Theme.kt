package com.example.overwatch.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColorScheme = darkColorScheme(
    primary = CyberPrimary,
    onPrimary = CyberBg,
    primaryContainer = CyberSurfaceCard,
    onPrimaryContainer = CyberPrimary,
    secondary = CyberSecondary,
    onSecondary = CyberBg,
    tertiary = CyberAccent,
    background = CyberBg,
    onBackground = CyberText,
    surface = CyberSurface,
    onSurface = CyberText,
    surfaceVariant = CyberSurfaceCard,
    onSurfaceVariant = CyberTextMuted,
    outline = CyberBorder,
    error = CyberError,
    onError = CyberText
)

@Composable
fun OverwatchTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = Typography,
        content = content
    )
}
