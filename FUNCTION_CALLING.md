# Function Calling in Alice

## What's New? 🎉

Alice now supports **proper function calling** (OpenAI-compatible tool use), making command execution more reliable and LangGraph-ready!

## How It Works

### Traditional Approach (Old)

- LLM outputs JSON like `{"action": "run_command", "command": "ls"}`
- We parse the text looking for JSON
- Unreliable if model doesn't format exactly right

### Function Calling (New) ✨

- We tell the LLM: "You have a tool called `execute_command`"
- LLM makes **structured tool calls** (not text)
- API returns proper tool call objects
- Much more reliable!

## Current Tools

### 1. `execute_command`

Execute terminal commands safely with confirmation.

**Parameters:**

- `command` (required): The base command (e.g., "ls", "git", "python")
- `args` (optional): Array of arguments (e.g., ["-la", "."])

**Example conversation:**

```
You: Show me what Python version I'm running
Assistant: I'll check that for you.

💻 Tool call: execute_command
   Command: python --version
   Execute this command? (y/n): y
   Executing...

   📤 Output:
   Python 3.11.5

Assistant: You're running Python 3.11.5.
```

## Configuration

Function calling is **enabled by default**. To disable it:

```env
# In your .env file
USE_FUNCTION_CALLING=false
```

## Agent Loop

When a tool is called:

1. LLM decides it needs to use a tool
2. Returns structured tool call (not text)
3. We show you the proposed command
4. You confirm (y/n)
5. We execute if safe and approved
6. Results go back to LLM
7. LLM responds with natural language

This can happen **multiple times** in one conversation turn (up to 5 iterations).

## Adding More Tools

To add a new tool:

### 1. Define the tool schema in `agent/tools.py`:

```python
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the contents of a file",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file"}
            },
            "required": ["file_path"]
        }
    }
}
```

### 2. Add to `TOOL_SCHEMAS` list

### 3. Implement in `execute_tool_call()` function

### 4. That's it! LangGraph-ready.

## LangGraph Compatibility

The tool definitions follow OpenAI's function calling format, which is **exactly** what LangGraph uses.

When you migrate to LangGraph:

- These tool schemas work as-is
- The `execute_tool_call()` function becomes your tool node
- The conversation loop becomes a StateGraph
- No refactoring needed!

## Supported APIs

- ✅ **LM Studio** - Full function calling support
- ✅ **Ollama** - Function calling support (newer models)
- ✅ **Any OpenAI-compatible API**

Some older Ollama models may not support function calling. If your model doesn't support it, set `USE_FUNCTION_CALLING=false` and it will fall back to the old JSON parsing method.
