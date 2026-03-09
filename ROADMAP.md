# Gedos Roadmap

## v0.9.14 — Web Tool ✅
- [x] Web tool via Scrapling (optional dependency)

## v0.9.15 — Jarvis Core ✅
- [x] Percepção Contínua — AXObserver event-driven (replaces 10s polling)
- [x] Contexto Persistente e Rico — ChromaDB + Ollama embeddings, 3-layer memory
- [x] Multimodalidade Real — Kokoro TTS local + gTTS fallback + Whisper STT

## v0.9.16 — Launch Gates (current)
- [x] pyproject.toml aligned with all optional dependencies
- [x] CI matrix Python 3.12 + 3.13
- [x] Fix datetime.utcnow() deprecated warnings
- [x] Coverage enforcement (60% global, critical modules tracked)
- [x] Smoke E2E tests
- [ ] Demo GIF recorded

## v1.0.0 — Stable Launch 🚀
- [x] CLI Mode + Onboarding
- [x] Pilot Mode (Telegram)
- [x] Copilot Mode (AX Tree)
- [x] Self-healing CI
- [x] MCP Server
- [x] Contextual Memory
- [x] Voice I/O
- [x] Natural language scheduling
- [x] Proactive Engine
- [x] Homebrew install
- [x] Security hardening (3 rounds)
- [x] LGPD/GDPR compliance
- [x] Audit log (JSONL)
- [x] /checklist e /auditlog

## v1.1.0 — Integrations
- [ ] Gmail
- [ ] Google Calendar
- [ ] Slack
- [ ] WhatsApp
- [ ] Extensible connector interface

## v1.2.0 — Linux Support
- [ ] Linux AX Tree alternative (AT-SPI)
- [ ] apt/snap package
- [ ] Linux CI matrix

## v1.3.0 — Multi-Mac
- [ ] Connect multiple Macs to one Telegram
- [ ] Route tasks to specific machine
- [ ] Shared pattern learning

## v2.0.0 — Gedos Web
- [ ] Web dashboard (Next.js)
- [ ] WebSocket relay
- [ ] Task history UI
- [ ] Pattern visualizer
- [ ] GEDOS.md editor in browser

## v3.0.0 — Gedos Cloud
- [ ] Hosted agent (no Mac required)
- [ ] gedos-agent daemon for Mac control
- [ ] Subscription model

## Future
- Gedos Mobile (iOS + Android)
- Gedos for Teams
- Gedos Enterprise
- Gedos Plugins marketplace
- Gedos API
