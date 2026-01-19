---
title: "Friday - Personal AI Assistant"
date: 2026-01-19
draft: false
tags: ["python", "ai", "llm", "self-hosted", "telegram"]
---

A sophisticated personal AI assistant designed to operate entirely on local hardware. No cloud dependencies - your data stays yours.

<!--more-->

## Overview

Friday is my personal AI assistant that runs on my homelab. It leverages the Hermes-4-14B model via vLLM and provides proactive awareness capabilities through multi-channel communication and extensive tool integration.

**Repository:** [github.com/arturgoms/friday](https://github.com/arturgoms/friday)

## Features

### Communication & Interaction
- Telegram bot interface with full conversation history
- Interactive CLI with 79 integrated tools across 13 modules
- Multi-channel session management
- Channel-agnostic session tracking with persistent SQLite storage

### Intelligence Capabilities
- Local LLM inference without cloud dependencies
- Context-aware responses using conversation history
- Tool chaining for complex multi-step queries
- Auto-snapshot system for data collection

### Proactive Awareness
- Health monitoring integration (Garmin/InfluxDB)
- Calendar-based awareness via CalDAV
- Portfolio tracking via DLP API
- Weather and environmental sensing
- Threshold-based notifications with quiet hour respect

### Specialized Systems
- Daily journal threads with voice transcription (Whisper)
- Scheduled reports (briefings, journal notes)
- Markdown formatting for Telegram compatibility
- Obsidian vault integration

## Tech Stack

- **Python 3.12+** with Pydantic-AI framework
- **vLLM** for model serving
- **SQLAlchemy** with SQLite for persistence
- **Typer** for CLI
- **CalDAV** for calendar sync
- **InfluxDB** for health data
- **Whisper** for voice transcription
- **systemd** for service management

## Why Local?

Running an AI assistant locally means:
- Complete privacy - no data leaves my network
- No API costs or rate limits
- Full control over the model and its behavior
- Works offline (except for external integrations)

The trade-off is hardware requirements (RTX 3090 in my case), but for a personal assistant that knows my schedule, health data, and daily routines, privacy is worth it.
