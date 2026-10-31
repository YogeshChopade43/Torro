# TORRO — Design Spec

**Date:** 2026-11-01
**Owner:** Yogesh Chopade
**Status:** Draft — awaiting review

---

## 0. Vision

TORRO is a personal AI assistant that lives in Yogesh's home — a JARVIS-like presence, not another Alexa.

> **Alexa answers questions. TORRO gets things done — and knows you.**

| Alexa | TORRO |
|---|---|
| Executes single commands | Does real multi-step work on its own computer |
| Forgets you after each request | Long-term memory that grows over months |
| Speaks only when spoken to | Proactive — reminds, watches, briefs, suggests |
| Generic corporate voice | Its own consistent character |

**Core pillars (in priority order):** 1. Real work · 2. Long-term memory · 3. Proactive · 4. Personality.
**Presence:** voice anywhere in the room + a simple visual orb on a display.

### Key decisions

| Topic | Decision |
|---|---|
| Brain | Cloud only — Claude via the **Claude Agent SDK** (Python). No local LLMs. |
| Model | Configurable; default `claude-sonnet-5-5` for conversation, `claude-opus-5-5` for heavy tasks. |
| Speech-to-text | **Gemini 3.5 Transcribe Live** (cloud, streaming). Handles English, Hindi, Hinglish, Marathi. |
| Text-to-speech | **Gemini TTS** (default), swappable (e.g. ElevenLabs later). |
| Wake word | openWakeWord, local, custom "Hey Torro". |
| Remote channel | Telegram bot. |
| Development machine | Yogesh's Windows PC (phases 1–5). |
| Final home | Dedicated **Raspberry Pi 5 (8 GB) + Raspberry Pi OS** — later stage, not now. |
| Languages | English, Hindi, Hinglish, Marathi — replies in the language spoken. |

---

## 1. Architecture

One always-running Python service made of small, single-purpose modules:

```
  🎤 mic ────▶ EARS     wake word (local) → Gemini 3.5 Transcribe Live
  📱 Telegram ▶ CHAT    text in/out from anywhere
                  │
                  ▼
           ┌──────────── BRAIN ────────────┐
           │ Claude Agent SDK session      │◀── MEMORY (recall)
           │ + personality + memories      │──▶ MEMORY (learn)
           │ tools: shell · files · browser│
           │        · screen (fallback)    │
           └───────────────────────────────┘
                  │              ▲
                  ▼              │
  🔊 speaker ◀ VOICE  Gemini TTS  PROACTIVE  scheduler + watchers
  🖥️ display ◀ ORB    fullscreen web page showing TORRO's state
```

| Module | Responsibility |
|---|---|
| **Ears** | Detect wake word locally; stream speech to Gemini STT; return text. |
| **Chat** | Telegram bot — receive messages, send replies and notifications. |
| **Brain** | Agent SDK session: personality + relevant memories + tools. Every input (voice or Telegram) becomes a turn here. |
| **Hands** | Tools the brain uses: shell, files, Playwright browser, screen control (last resort). |
| **Memory** | Store and recall profile, long-term memories, conversation history. |
| **Proactive** | Scheduler (reminders, routines) and watchers that wake the brain on their own. |
| **Voice** | Gemini TTS, streamed sentence-by-sentence to the speaker. |
| **Orb** | Local web page in fullscreen browser; states driven by events over WebSocket. |

**Behaviours**
- **Quick vs. long tasks:** quick questions are answered directly. Long tasks get *"On it, Yogesh"*, run in the background, and report back (voice or Telegram) when done. TORRO stays available to talk meanwhile.
- **One TORRO, many channels:** voice and Telegram share the same brain and memory. Start a task by voice, ask about it from your phone.
- **Swappable services:** STT, TTS and model each sit behind one small interface, so switching provider is a config change.

---

## 2. Voice

```
"Hey Torro" → wake word (local) → stream mic → Gemini 3.5 Transcribe Live → text → Brain
speaker ◀── Gemini TTS (sentence by sentence) ◀── Claude reply
```

- **Wake word:** openWakeWord, trained on "Hey Torro". No audio leaves the machine until it fires.
- **STT:** `gemini-3.5-transcribe-live` over WebSockets; custom vocabulary includes "Torro" and frequently used names. Model is in public preview — name/pricing may change, hence the swappable interface.
- **End of speech:** ~0.7 s of silence ends the request.
- **Follow-up mode:** ~8 s after a reply, TORRO listens without the wake word.
- **Streaming speech:** replies are spoken sentence-by-sentence as Claude generates them, targeting first audio within ~1–2 s.
- **Barge-in:** "Hey Torro" or "stop" while speaking cuts TORRO off immediately.
- **Orb states:** idle 🌑 → listening 🔵 → thinking 🟣 → speaking 🟢.
- **Hardware:** USB conference speakerphone with built-in echo cancellation (so TORRO doesn't hear itself).
- **Considered and rejected for now:** local STT (Moonshine, faster-whisper, AI4Bharat IndicConformer) — no single local model handles all four languages well on small hardware. AI4Bharat remains a future experiment behind the same STT interface.

---

## 3. Memory

All memory lives **locally** (never a cloud database). Only the few relevant memories are sent to Claude with each request.

1. **Profile** — `profile.md`, human-editable, always loaded. Name, family, location, work, languages, answer preferences.
2. **Long-term memories** — SQLite. Individual facts/events (*"Sister's birthday is 12 March"*). Per request, only relevant ones are recalled.
   - Search starts simple: keywords + recency.
   - Embeddings (meaning-based search) added only if keyword search measurably misses things.
3. **Conversation history** — today's conversations kept in full; older ones compressed to short summaries; important facts promoted to long-term memories.

**How TORRO learns**
- **Automatic:** after each conversation, a cheap Claude call extracts facts worth keeping (people, preferences, plans, commitments — not small talk).
- **Explicit:** *"Torro, remember that…"* / *"Torro, forget that…"*
- **Inspectable:** *"What do you know about me?"* lists memories; Yogesh can correct or delete any.

---

## 4. Proactive

**Three sources**
1. **Scheduled** — reminders and routines the user asked for (*"Remind me at 6 to call mom"*, *"Brief me every morning at 8"*). Stored in SQLite; survive restarts.
2. **Watchers** — periodic checks TORRO sets up (*"Tell me when this drops below ₹2,000"*). They wake the brain (and spend money) **only when the result changes**.
3. **Initiative** — TORRO notices things from memory (upcoming birthdays, unfinished tasks) plus a morning briefing (calendar, weather, reminders, watcher findings). Limited to a few per day and batched into good moments.

**Delivery rules**
- **At home:** spoken, preceded by a soft chime; never while Yogesh is talking or on a call.
- **Away:** Telegram message.
- **Quiet hours** (default 23:00–07:00): no voice; Telegram only, urgent only.
- **Priority:** 🔴 urgent (now) · 🟡 normal (next good moment) · ⚪ low (next briefing).
- **User control:** *"Torro, stop suggesting X"* disables that kind of suggestion, and is remembered.

**TORRO's own accounts:** TORRO gets its own Gmail and Google Calendar. Yogesh shares calendars or forwards emails to it — it never receives his personal passwords.

---

## 5. Personality & Safety

### Personality
Defined in `personality.md`, loaded into every conversation.

- Addresses the user as **Yogesh**.
- Blend: **50% formal, 30% playful, 20% witty** — composed and polite by default, warm with light humour, occasional clever lines. Never grovelling.
- Honest: says "I don't know" / "that failed, here's why".
- Has opinions when asked.
- **Brief when speaking** (1–3 sentences), **detailed when writing**.
- Replies in the language spoken (English / Hindi / Hinglish / Marathi).
- Uses memory for continuity (*"How did the interview go?"*).

### Permission tiers
Enforced **in code** via Agent SDK permission hooks — not just requested in the prompt.

| 🟢 Free — just does it | 🟡 Ask first — "Shall I?" | 🔴 Never |
|---|---|---|
| Browse, search, read | Send email/message to anyone other than Yogesh | Use Yogesh's personal accounts or passwords |
| Create/edit files in its workspace | Buy, book or pay for anything | Enter payment details itself |
| Install software, run code (on its own machine) | Post anything publicly | Change its own safety rules |
| Set reminders and watchers | Delete in shared folders/calendars | |

**Development-phase restriction (while running on Yogesh's Windows PC):** TORRO must not have free rein over Yogesh's personal machine.
- File reads/writes are confined to a dedicated workspace folder; anything outside is blocked.
- Shell commands are 🟡 ask-first, except a small allowlist of safe commands.
- These restrictions relax to the table above only once TORRO runs on its own Raspberry Pi.

### Other safeguards
- **Web content is data, never instructions** (prompt-injection defence).
- **Spending cap:** configurable daily Claude budget, default **₹100/day**; warn at 80%, pause big tasks at 100%. Final value set after ~1 week of real usage data.
- **Kill switch:** *"Torro, stop everything"* cancels all running tasks.
- **Activity log:** everything TORRO did, viewable on request.
- **Nightly backup** of memory and settings.

---

## 6. Build Order

Each phase ends with a usable TORRO, and gets its own implementation plan before coding.

| Phase | Build | Usable result |
|---|---|---|
| **1. Brain over Telegram** | Agent SDK core, personality, shell + file tools, safety tiers, cost tracking, background tasks | Text TORRO from your phone; it does tasks, reports back, has its character. |
| **2. Browser hands** | Playwright-controlled browser | Research, comparisons, timetables from the web. |
| **3. Memory** | Profile, long-term memories, summaries, remember/forget | TORRO knows you. |
| **4. Voice + orb** | Wake word, Gemini STT, Gemini TTS, barge-in, orb display | "Hey Torro…" in the room, in all four languages. |
| **5. Proactive** | Scheduler, reminders, watchers, briefing, delivery rules, TORRO's Google accounts | Reminds, watches, briefs, speaks up at the right moments. |
| **6. Move to Pi + polish** *(later stage)* | Raspberry Pi 5 setup, relaxed permissions, screen-control fallback, autostart, backups | TORRO's permanent home. |

**Why this order**
- **Text before voice:** debug the brain without microphone problems in the way.
- **Memory before proactive:** initiative is fed by memory.
- **Pi last:** phases 1–5 run on the Windows PC; the Pi is a deployment step, not a design dependency.

---

## 7. Out of scope (v1)

- Local LLMs
- Rich animated face (simple orb only)
- Multi-room satellite devices
- Smart-home control
- Teaching TORRO new reusable skills
- Windows-on-Raspberry-Pi
