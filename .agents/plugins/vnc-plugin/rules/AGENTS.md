# VNC Bridge & Remote Agent Operation Rules

When the VNC Bridge plugin is active:

1. **Remote Injected Prompts**: Messages injected via the VNC Bridge or Desktop Controller will arrive as regular user turns or notifications. Acknowledge instructions clearly and prioritize them.
2. **Window Capture Awareness**: The agent can capture screenshots of its own window or the desktop using `vnc_capture_screen` to verify GUI changes or visual tasks.
3. **Security**: The VNC and Web streaming endpoints are bound to the local network interfaces. Inform the user if external port forwarding or additional authentication is needed when exposing beyond the LAN.
