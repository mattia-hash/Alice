# 🧠 Local Voice Assistant (Offline Terminal AI)

A **fully local personal assistant** that runs directly on your computer — no cloud, no external APIs, no data leaving your device.

This assistant allows **voice-based interaction**, **offline reasoning via a local LLM**, **safe terminal command execution**, and **conversation history** stored in a local database.

---

## 🚀 Overview

The goal is to create an offline, privacy-first assistant that can:
- Listen to the user through the microphone  
- Understand speech using a local ASR model  
- Respond vocally using a local TTS model  
- Think and reason using a local LLM (via Ollama)  
- Execute terminal commands safely (with confirmation)  
- Store and recall chat history locally  

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────┐
│              Voice Assistant Loop            │
│----------------------------------------------│
│  🎙️  Speech Input (ASR - faster-whisper)     │
│  🧠  LLM Reasoning (Ollama local model)       │
│  💻  Command Execution (sandboxed)            │
│  💬  TTS Output (Piper / Coqui)              │
│  🗄️  Local Memory (SQLite + optional vector) │
└──────────────────────────────────────────────┘
```

---

## ⚙️ Core Components

### 1. Speech-to-Text (ASR)
- **Technology:** `faster-whisper`
- **Purpose:** Transcribe microphone input to text using a Whisper model locally.
- **Extras:** Uses `webrtcvad` for voice activity detection (push-to-talk initially).

### 2. LLM Inference (Reasoning)
- **Backend:** `Ollama` on `localhost:11434`
- **Models:** `qwen2.5:3b`, `mistral:7b`, or `llama3.1:8b`
- **Purpose:** Generate assistant responses or propose commands.
- **Response schema:**
  ```json
  {
    "action": "respond",
    "text": "Here's your system info."
  }
  ```
  or
  ```json
  {
    "action": "run_command",
    "command": "ls",
    "args": ["-la", "/home/mattia"]
  }
  ```

### 3. Command Execution
- **Language:** Python `subprocess`
- **Security model:**
  - Allowlist of safe commands (`ls`, `cat`, `docker`, `git`, etc.)
  - No pipes, redirections, or dangerous operators
  - Requires explicit confirmation before running
  - Output truncated and logged to DB
- **Optional sandbox:** use `firejail` or `bubblewrap` for isolation

### 4. Text-to-Speech (TTS)
- **Options:**
  - **Piper:** small, fast, high-quality offline voices
  - **Coqui TTS:** higher fidelity, larger footprint
- **Pipeline:** LLM → text → WAV → playback via `aplay` or `sounddevice`

### 5. Local Memory
- **Database:** SQLite  
  Stores:
  - Conversations (`messages`)
  - Commands (`commands`)
- **Schema:**
  ```sql
  messages(id, session_id, role, content, created_at)
  commands(id, session_id, cmd, args_json, approved, exit_code, stdout, stderr, created_at)
  ```
- **Optional Vector Memory:** via Chroma or LanceDB for long-term recall, with local embeddings from `nomic-embed-text`.

---

## 🧩 Folder Structure

```
local-assistant/
├── app.py                 # main orchestrator loop
├── agent/
│   ├── llm.py             # Ollama chat interface
│   ├── asr.py             # speech recognition
│   ├── tts.py             # speech synthesis
│   ├── tools.py           # terminal command executor
│   └── memory.py          # SQLite + vector memory
├── data/
│   ├── db.sqlite          # chat and command history
│   └── voices/            # Piper voice models
├── models/                # Ollama models (auto-downloaded)
├── requirements.txt
└── .env                   # environment config (LLM_MODEL, etc.)
```

---

## 🧰 Tech Stack

| Layer | Technology | Purpose |
|-------|-------------|----------|
| LLM | **Ollama (Qwen/Mistral/LLaMA)** | Local reasoning |
| ASR | **faster-whisper** | Offline speech recognition |
| TTS | **Piper / Coqui TTS** | Offline speech synthesis |
| Audio | **sounddevice / PyAudio / webrtcvad** | Microphone & VAD |
| DB | **SQLite / Chroma** | Conversation + memory storage |
| Command Runner | **subprocess (safe mode)** | Terminal execution |
| Language | **Python 3.11+** | Core logic |
| UI | CLI / TUI (later: Qt or Gradio) | Interaction |

---

## 🔐 Privacy & Security

- No internet connections: **all inference is local**  
- Allowlist-based terminal access  
- Confirmation before any command runs  
- SQLite stored in user folder (`~/.local-assistant/db.sqlite`)  
- Optionally encrypted at rest (SQLCipher)  

---

## 🏁 Setup Instructions

1. **Install Ollama**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull qwen2.5:3b
   ```

2. **Create Python environment**
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -U pip
   pip install faster-whisper webrtcvad sounddevice python-dotenv chromadb
   pip install TTS  # optional, for Coqui TTS
   ```

3. **Download a Piper voice (optional)**
   ```
   voices/it_IT-riccardo-x_low.onnx
   ```

4. **Run the app**
   ```
   python app.py
   ```

---

## 🧱 System Prompt Example

> You are a local AI assistant running on Mattia’s computer.  
> You may propose safe terminal commands but must always ask for confirmation before executing them.  
> Speak concisely and in Italian unless instructed otherwise.  
> Everything you do stays offline.

---

## 💬 Example Interaction

**User:** “What files do I have here?”  
**Assistant (LLM):**
```json
{
  "action": "run_command",
  "command": "ls",
  "args": ["-la", "."]
}
```
**App:** “I’m about to run `ls -la .`. Do you confirm? (y/n)”  
**User:** “Yes.”  
**Assistant:** *runs the command, reads the output summary aloud.*

---

## 🌱 Future Enhancements

- Wake-word detection (“Hey Marcello”) via `openWakeWord`  
- Vector memory summarization and retrieval  
- Local calendar or file plugins  
- Simple desktop GUI (Gradio, PyQt, or Electron)  
- Integration with Boox or Raspberry Pi  

---

## 🧩 License

MIT License (customize as needed)

---

## ✨ Credits

- **Ollama** for local LLM hosting  
- **faster-whisper** for ASR  
- **Piper / Coqui TTS** for speech synthesis  
- **Mattia’s idea & architecture** for a truly private local assistant  
