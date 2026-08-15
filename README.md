# memory-pet (AI version)

A companion that runs a real small local LLM, develops a personality over time,
tracks mood, and remembers multiple people separately. Runs fully offline, no
account, no cloud.

## How it works

- `bin/llama-server` — runs the actual language model (you provide this, see below).
- `server.py` — Python backend. Tracks personality traits, mood, and per-user
  memory (likes / dislikes / notes), builds a prompt each turn, and calls the
  model. Pure Python standard library, no `pip install` needed.
- `web/` — the chat interface (profile picker + chip-pet screen).
- `data/` — where memory gets saved, as plain JSON files. This is what makes
  the pet "remember almost everything" — one file per person, growing forever,
  fed back into every conversation as relevant.

**Two one-time downloads you need to do yourself** (my sandbox can't reach
these hosts):

### 1. llama-server binary
Go to https://github.com/ggml-org/llama.cpp/releases, grab the build for your
OS (Windows: `llama-*-bin-win-*.zip`), unzip it, and copy `llama-server.exe`
(plus its `.dll` files, Windows needs them alongside it) into `bin/`.

### 2. A model, under 1.5 GB
Recommended: **Qwen2.5-1.5B-Instruct**, Q4_K_M quantization, GGUF format
(~1.0 GB) — good personality/instruction-following for its size. Search
"Qwen2.5-1.5B-Instruct-GGUF" on Hugging Face, download the `Q4_K_M.gguf`
file, drop it in `models/`. A smaller/faster option: Llama-3.2-1B-Instruct
GGUF (~0.8 GB).

Then:
- **Windows:** double-click `start.bat`
- **Mac/Linux:** `chmod +x start.sh && ./start.sh`

It prints two URLs — one for this PC, one for your phone (same wifi).

## About the "runs on mobile too" part

Phones can't run `.exe`/native `llama-server` binaries directly off a USB
stick the way a PC can — there's no bundling around that. What actually works
here: the PC does the model inference, and the phone just opens the web page
in its browser over local wifi, same as any other device on the network. So
it's one shared brain, multiple screens — not two independent installs. If
you ever want the model to also run standalone on the phone (no PC needed),
that requires a proper Android app (e.g. via Termux + llama.cpp) — different,
heavier project, happy to help with it if you want it later.

## What's simulated vs real

- The **language model** is real and running locally — this isn't scripted
  replies.
- "Huge context window / remembers everything" — done via retrieval, not by
  stuffing the whole history into the model each time (tiny models get
  noticeably worse at long raw context). Each person's likes/dislikes/notes
  are stored permanently in their JSON file and the most relevant ones get
  pulled into the prompt every message.
- "Personality" and "feelings" — a small numeric state (warmth, playfulness,
  curiosity, patience, mood) that drifts slowly based on how you talk to it,
  and gets described to the model each turn so its tone actually shifts. It's
  a state machine wrapped around the LLM, not the model itself "having"
  emotions — worth being upfront about that.
- **Multi-user** — the picker screen on load; each person gets their own
  memory file and affinity score, the pet's core personality is shared
  across everyone (like a real pet recognizing different people).
