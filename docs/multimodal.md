# Multimodal

## Overview

Multimodalidade Real in Gedos means local voice input and voice output working together:

- STT: Whisper (local, already implemented)
- TTS: Kokoro (local, offline, high quality) with gTTS fallback (online)

## Why Kokoro over gTTS

- Fully offline
- Significantly higher voice quality
- No Google dependency
- Apache 2.0 license

## Setup

```bash
pip install kokoro soundfile numpy
```

No manual model download is required. Kokoro handles model setup automatically.

## Usage

Voice behavior is automatic:

- User sends Telegram voice message -> Gedos transcribes and executes
- Gedos replies in voice mode -> TTS response is generated and sent

## Fallback chain

Kokoro -> gTTS -> text (if both fail)

## Requirements

- Python 3.10+
- macOS or Linux
