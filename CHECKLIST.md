# Gedos v0.9.0 Pre-Launch Checklist

This checklist must be completed before v1.0.0 public launch.

---

## Tests
- [x] All unit tests passing (`pytest tests/`)
- [x] Integration tests passing (`pytest tests/integration/`)
- [ ] Smoke test on fresh clone (another machine)
- [ ] /task cancel works mid-execution on all agent types

---

## Documentation
- [x] README.md complete and accurate
- [x] docs/setup-ollama.md reviewed
- [x] docs/examples.md with 5 real examples
- [x] CONTRIBUTING.md exists
- [x] CHANGELOG.md up to date
- [ ] Demo GIF recorded and added to README

---

## Security
- [x] Input sanitization implemented
- [x] Rate limiting active (10 cmd/min)
- [x] API keys validated on startup
- [x] No secrets logged anywhere
- [ ] Manual security audit of shell command execution

---

## Stability
- [ ] AX Tree cache correctness validated
- [ ] Memory layer handles concurrent writes
- [ ] /task cancel interrupts gracefully
- [ ] Long-running sessions tested (no memory leaks)
- [ ] Telegram reconnection tested

---

## UX Polish
- [x] Rich CLI output with colors
- [x] /start onboarding clear for new users
- [x] /help context-aware (Pilot vs Copilot)
- [ ] All error messages user-friendly
- [ ] Consistent formatting across all commands

---

## Release
- [ ] Version bumped to 0.9.0
- [ ] CHANGELOG.md updated
- [ ] Git tag v0.9.0 created
- [ ] GitHub release published
- [ ] All commits pushed to main

---

## Pre-v1.0 (Before Public Launch)
- [ ] Real demo GIF recorded (Kap/Gifox)
- [ ] README tested from fresh clone by external user
- [ ] Zero critical issues open
- [ ] Ollama setup guide validated on clean Mac
- [ ] Performance benchmarks documented

---

**Status**: v0.9.0 RC in progress  
**Last updated**: 2026-03-01
