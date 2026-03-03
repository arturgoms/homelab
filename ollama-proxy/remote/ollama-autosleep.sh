#!/bin/bash
# Don't suspend if models are loaded (ollama unloads after 5min idle)
MODELS_LOADED=$(curl -sf http://localhost:11434/api/ps 2>/dev/null | grep -c '"model"' || true)
[ "${MODELS_LOADED:-0}" -gt 0 ] && exit 0

# Don't suspend if someone is logged in via SSH
LOGGED_IN=$(who | wc -l)
[ "$LOGGED_IN" -gt 0 ] && exit 0

logger -t ollama-autosleep "Ollama idle, suspending"
systemctl suspend
