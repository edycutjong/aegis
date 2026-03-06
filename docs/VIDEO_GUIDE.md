# Aegis Demo Video — Complete Production Guide

> Step-by-step guide to produce a polished 2:30 demo video with AI voiceover. All tools are **100% free**.

---

## Overview

```
Raw .webm (Playwright)
    ↓
Convert to MP4 (ffmpeg)
    ↓
AI Voiceover (free tool → MP3)
    ↓
Background Music (YouTube Audio Library)
    ↓
CapCut or Google Vids: combine video + audio + music + text overlays + zoom edits
    ↓
Export 1080p MP4
    ↓
Upload to Loom or YouTube (unlisted)
    ↓
Embed on edycu.dev/work/aegis + link in README.md
```

---

## Step 1: Record the Demo (Done ✅)

The Playwright script at `scripts/record-demo.mjs` automates the recording.

```bash
# Clear cache
curl -X DELETE http://localhost:8000/api/cache

# Record
node scripts/record-demo.mjs
```

Output: `scripts/aegis-demo.webm`

---

## Step 2: Convert to MP4

```bash
brew install ffmpeg  # if not installed
ffmpeg -i scripts/aegis-demo.webm -c:v libx264 -crf 18 scripts/aegis-demo.mp4
```

---

## Step 3: Generate AI Voiceover (Free Options)

The ElevenLabs "Josh - Deep, Fluent and Clear" voice requires a paid plan. Here are **free alternatives**:

| Tool | Cost | Quality | How to Use |
|---|---|---|---|
| **Google Cloud TTS** | Free $300 credits (Google One Ultra) | ⭐⭐⭐⭐⭐ | [cloud.google.com/text-to-speech](https://cloud.google.com/text-to-speech) → Try API → Studio voices |
| **Google NotebookLM** | Free (Ultra plan) | ⭐⭐⭐⭐ | Paste script as a source → Generate Audio Overview |
| **Microsoft Edge Read Aloud** | Free | ⭐⭐⭐⭐ | Open script in Edge → Right-click → Read Aloud → Record with OBS/QuickTime |
| **NaturalReader** | Free (limited) | ⭐⭐⭐⭐ | [naturalreaders.com](https://www.naturalreaders.com) → Online → Paste script → Download |
| **TTSMaker** | Free | ⭐⭐⭐ | [ttsmaker.com](https://ttsmaker.com) → Paste script → Select US English male → Download |
| **CapCut AI Narrator** | Free | ⭐⭐⭐ | Built into CapCut Desktop → Add text → AI voiceover button |
| **ElevenLabs Free Tier** | Free (10 min/month) | ⭐⭐⭐⭐⭐ | 2:30 script fits within free tier if you haven't used it yet |

### Recommended: Google Cloud TTS (you have Ultra)

1. Go to [Cloud Console](https://console.cloud.google.com/speech/text-to-speech)
2. Select voice: **en-US-Studio-M** (male, studio quality)
3. Paste each section of the script → Synthesize → Download
4. Combine audio clips in CapCut

### Alternative: CapCut Built-in (Easiest)

1. Import the MP4 into CapCut
2. Add text captions for each section
3. Select text → Click **"Text to Speech"** → Pick a male voice
4. CapCut generates the voiceover directly on the timeline

---

## Step 4: The Full Voiceover Script

Paste this into your AI voice tool. Each section maps to a part of the Playwright recording.

---

### [0:00 – 0:15] Part 1: Hook

> This is Aegis — an autonomous enterprise action engine. It's a multi-agent AI system that investigates complex support tickets, reasons through data, and most importantly — waits for human approval before taking any action.

---

### [0:15 – 0:25] Part 2: Submit Ticket

> Let's walk through a real workflow. A customer reports a duplicate charge on their Pro plan. I submit the ticket, and the agent starts working immediately. Watch the ThoughtStream on the right — every step streams to the UI in real-time.

---

### [0:25 – 0:40] Part 3: Triage + Customer Validation

> The Triage Agent classifies the intent as billing with 95 percent confidence and routes it to the Investigator. The Investigator Agent validates the customer identity — it handles eight edge cases including typo correction, fuzzy name matching, and disambiguation when multiple customers share a name.

---

### [0:40 – 0:55] Part 4: SQL + Self-Healing

> Next, the agent generates SQL from natural language and executes it against our PostgreSQL database on Supabase. If the query fails — maybe a wrong column name — it self-heals by feeding the error message back to the LLM for correction, up to three retries. This is how you build resilient AI systems.

---

### [0:55 – 1:05] Part 5: Knowledge Search

> The Knowledge Agent then searches internal policy documents for the relevant refund guidelines. It finds the matching policy and passes everything — the SQL results, the customer data, and the policy — to the Resolution Agent.

---

### [1:05 – 1:25] Part 6: HITL Approval (The Money Shot)

> Here's where it gets interesting. The Resolution Agent proposes a twenty-nine dollar refund — but it does not execute it. The entire LangGraph workflow literally pauses. This approval modal appears on screen. The AI cannot proceed without a human clicking Approve. This is the number one feature enterprise companies are looking for. Not smarter AI — trusted AI.

---

### [1:25 – 1:35] Part 7: Approve + Resolution

> I approve the action. The workflow resumes, executes the refund recommendation, and generates a resolution summary. Total cost for this entire multi-agent workflow — including four LLM calls, a database query, and a document search — less than one cent.

---

### [1:35 – 1:50] Part 8: Dev Mode + Observability

> Switching to Dev Mode reveals the full technical trace — model names, latency per step, and color-coded agent badges. The observability dashboard on the right tracks token usage, cost per request, model distribution, and cache hit ratios. Every single metric a CTO needs to trust this system in production.

---

### [1:50 – 2:10] Part 9: Semantic Cache

> Now watch this. I submit the exact same ticket again. This time, the semantic cache recognizes it. Redis serves the answer in under fifty milliseconds. Zero API calls. Zero cost. Zero latency. If your users ask the same question a hundred times, it costs the company exactly zero dollars. This is how you protect profit margins at scale.

---

### [2:10 – 2:30] Part 10: Close

> Aegis is built with FastAPI and LangGraph on the backend, Next.js and React on the frontend, Redis for caching, and Supabase for the database. It supports dynamic model routing across Groq, GPT-4, and Gemini — routing cheap models for simple tasks and expensive models only when reasoning demands it. The entire codebase has one hundred percent test coverage, a Docker Compose one-command setup, and full LangSmith tracing. Check out the architecture breakdown and source code at the links on screen.

---

## Step 5: Background Music

1. Go to [YouTube Audio Library](https://studio.youtube.com/channel/UC/music) (requires YouTube account)
2. Search: **"ambient technology"** or **"lo-fi chill"**
3. Download a track — must be **royalty-free**
4. Set volume to **10–15%** behind the voiceover

---

## Step 6: Edit & Assemble

### Import into CapCut Desktop (Free) or Google Vids

1. **Import** the MP4 video
2. **Import** the AI voiceover MP3
3. **Import** the background music
4. Drag all three onto the timeline

### Editing Checklist

| # | Edit | Why |
|---|---|---|
| 1 | **Speed up** typing and loading to 1.5–2x | Kill dead air — CTOs don't wait |
| 2 | **Zoom in** on HITL modal (150%) | The #1 money shot |
| 3 | **Zoom in** on cost metric after resolution | Proves cost awareness |
| 4 | **Zoom in** on cache hit instant response | Proves efficiency |
| 5 | **Sync** voiceover timing to video actions | Each script section matches a video part |
| 6 | **Add text overlays** (see table below) | Reinforces narrative on mute |
| 7 | **Add music** at 10–15% volume | Professional polish |
| 8 | **Add title card** (3 seconds, before video) | First impression |
| 9 | **Add end card** (5 seconds, after video) | GitHub + portfolio links |
| 10 | **Trim total** to 2:00–2:30 | Anything longer kills engagement |

### Text Overlays

| Timestamp | Overlay Text |
|---|---|
| 0:00 | `⛊ Aegis` |
| 0:02 | `Autonomous Enterprise Action Engine` |
| 0:03 | `Multi-Agent AI · Human-in-the-Loop Security` |
| 0:25 | `🏷 Triage Agent → Intent: Billing (95%)` |
| 0:35 | `🔍 Investigator → 8 validation edge cases` |
| 0:45 | `💾 Self-Healing SQL → 3× auto-retry` |
| 0:55 | `📚 Knowledge Agent → Policy search` |
| 1:10 | `⏸ WORKFLOW PAUSED — Human Approval Required` |
| 1:30 | `Total cost: ~$0.009` |
| 2:05 | `⚡ Semantic Cache → $0.00 · <50ms` |
| 2:15 | `github.com/edycutjong/aegis` |
| 2:20 | `edycu.dev/work/aegis` |
| 2:22 | `FastAPI · LangGraph · Next.js · Redis · LangSmith` |

### The 3 "Money Shots" (Zoom + Hold)

These 3 moments are what make a CTO say *"hire this person"*:

1. **HITL Modal** — Zoom 150%, hold 4 seconds, text: *"AI cannot proceed without human approval"*
2. **Cost: $0.009** — Zoom 130%, hold 3 seconds, text: *"Total cost per workflow"*
3. **Cache Hit** — Zoom 130%, hold 3 seconds, text: *"$0.00 — zero API calls"*

---

## Step 7: Export

- Format: **MP4**
- Resolution: **1920×1080 (1080p)**
- Frame rate: **30fps**

---

## Step 8: Upload & Embed

### Option A: Loom (Recommended)

1. Go to [loom.com](https://www.loom.com) → Upload video
2. Copy the share link
3. Embed on case study: `edycu.dev/work/aegis`

### Option B: YouTube (Unlisted)

1. Upload to YouTube as **Unlisted**
2. Title: *"Aegis — Autonomous Enterprise Action Engine | Demo"*
3. Description: Link to `edycu.dev/work/aegis` and `github.com/edycutjong/aegis`
4. Embed the YouTube player on your case study page

### Update README.md

Add the video link to the Demo section of the README.

---

## Re-Recording

If you update the UI or want a fresh recording:

```bash
# Ensure Aegis is running
docker-compose up -d

# Clear cache
curl -X DELETE http://localhost:8000/api/cache

# Re-record
node scripts/record-demo.mjs

# Convert
ffmpeg -i scripts/aegis-demo.webm -c:v libx264 -crf 18 scripts/aegis-demo.mp4
```
