# Alice - Local LLM Assistant Usage Guide

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install python-dotenv requests
```

Or using the requirements file:

```bash
pip install -r requirements.txt
```

### 2. Configure Your LLM

Your `.env` file should already be configured with:

```env
LLM_COMPLETIONS_URL=http://localhost:1234/v1/chat/completions
MODEL_NAME=qwen2.5:3b
```

**For LM Studio:** Make sure LM Studio is running and a model is loaded on port 1234.

**For Ollama:** Change the URL to:

```env
LLM_COMPLETIONS_URL=http://localhost:11434/api/chat
MODEL_NAME=qwen2.5:3b
```

### 3. Run the Assistant

```bash
python app.py
```

---

## 💬 Using the Chat Interface

### Basic Chat

Simply type your messages and press Enter:

```
You: What's the weather like?
Assistant: I don't have access to weather data, but I can help you...
```

### Command Execution

Ask the assistant to run commands:

```
You: What files are in this directory?
Assistant: {"action": "run_command", "command": "ls", "args": ["-la"]}

💻 Proposed command: ls -la
Execute this command? (y/n): y
Executing...
📤 Output:
total 48
drwxr-xr-x  8 user  staff   256 Oct 21 23:10 .
drwxr-xr-x 15 user  staff   480 Oct 21 22:00 ..
...
```

### Special Commands

- `exit`, `quit`, `bye` - End the conversation
- `clear` - Clear conversation history (start fresh)

---

## 🔒 Security Features

### Command Allowlist

Only these commands are permitted:

- File operations: `ls`, `cat`, `pwd`, `find`, `grep`, `head`, `tail`, `wc`
- System info: `date`, `whoami`, `uname`, `df`, `du`, `ps`, `which`
- Development: `git`, `docker`, `python`, `pip`, `node`, `npm`, `cargo`

### Safety Checks

- No shell operators: `&&`, `||`, `|`, `>`, `<`, `;`, backticks
- User confirmation required before execution
- Output truncated to 10KB max
- 30-second timeout per command

### Expanding the Allowlist

Edit `agent/tools.py` to add more commands to `ALLOWED_COMMANDS`:

```python
ALLOWED_COMMANDS = {
    'ls', 'cat', 'pwd', 'echo', 'date', 'whoami',
    'git', 'docker', 'ps', 'df', 'du', 'find',
    # Add your commands here
    'your_command', 'another_command'
}
```

---

## 🗄️ Database & Memory

### Conversation Storage

All conversations are stored in `data/db.sqlite`:

- **messages** table: Chat history with timestamps
- **commands** table: Executed commands with results

### Viewing History

You can query the database directly:

```bash
sqlite3 data/db.sqlite
```

```sql
-- View recent messages
SELECT * FROM messages ORDER BY created_at DESC LIMIT 10;

-- View executed commands
SELECT * FROM commands WHERE approved = 1;
```

---

## 🔧 Advanced Configuration

### Custom System Prompt

Add to your `.env` file:

```env
SYSTEM_PROMPT=You are Alice, a helpful assistant specialized in Python development. Always write clean, documented code.
```

### Show Model Thinking Process

Some models (like DeepSeek-R1) output their reasoning in `<think>` tags. By default, these are **hidden** for cleaner output. To show them in dimmed gray text, add to your `.env`:

```env
SHOW_THINKING=true
```

**Example output with thinking shown:**

```
Assistant: [thinking: User said hello, I should greet them...] Hello! How can I help you today?
```

### Temperature & Parameters

Currently hardcoded to `0.7`. To customize, edit `app.py`:

```python
for chunk in llm.stream_chat(messages, temperature=0.9):
```

---

## 🧩 LangGraph Migration Path

This codebase is designed to be LangGraph-compatible. Here's how components map:

### Current Architecture

```
User Input → LLM Response → Action Parser → Tool Execution → Response
```

### Future LangGraph Graph

```python
from langgraph.graph import StateGraph

graph = StateGraph(AgentState)
graph.add_node("llm", call_llm)           # Uses agent/llm.py
graph.add_node("tools", execute_tools)    # Uses agent/tools.py
graph.add_edge("llm", "tools")
graph.add_conditional_edges("tools", should_continue)
```

### Tool Definitions

The functions in `agent/tools.py` are already structured as LangGraph tools:

```python
from agent.tools import execute_command

# Already a valid LangGraph tool signature
result = execute_command(command="ls", args=["-la"])
```

---

## 🚧 Future Enhancements

Based on the original README, these features can be added:

1. **Voice Input (ASR)** - Add `agent/asr.py` using `faster-whisper`
2. **Voice Output (TTS)** - Add `agent/tts.py` using Piper or Coqui
3. **Vector Memory** - Add ChromaDB integration for long-term recall
4. **LangGraph Agent Loop** - Convert to stateful agent with tool selection
5. **Web UI** - Add Gradio or Streamlit interface
6. **Wake Word** - Add "Hey Alice" activation

---

## 🐛 Troubleshooting

### "LLM_COMPLETIONS_URL not set"

Make sure your `.env` file exists in the project root with the URL configured.

### Connection errors

- **LM Studio:** Ensure the server is running and listening on port 1234
- **Ollama:** Ensure Ollama service is running (`ollama serve`)

### Streaming not working

- Check that your LLM backend supports streaming
- For Ollama: Make sure you're using `/api/chat` endpoint
- For LM Studio: Make sure you're using `/v1/chat/completions` endpoint

### Commands not executing

- Check if the command is in the allowlist (`agent/tools.py`)
- Verify no blocked patterns in command or arguments
- Check terminal output for specific error messages

---

## 📝 Example Session

```
╔════════════════════════════════════════════╗
║     🧠 Local LLM Assistant (Alice)        ║
╚════════════════════════════════════════════╝

Model: qwen2.5:3b
Endpoint: http://localhost:1234/v1/chat/completions
Session: session_20251021_231045_a1b2c3d4

Type 'exit', 'quit', or 'bye' to end the conversation.
Type 'clear' to clear conversation history.

You: Hello! Can you tell me what Python version I'm using?
Assistant: I can help you check that! Let me run a command to find out.

💻 Proposed command: python --version
Execute this command? (y/n): y
Executing...
📤 Output:
Python 3.11.5

You: Thanks!
Assistant: You're welcome! You're running Python 3.11.5. Is there anything else I can help you with?

You: exit
👋 Goodbye!
```
