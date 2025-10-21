# Windows Command Reference

Alice is now Windows-aware! Here are the commands you can use on Windows.

## Shell Execution

Alice intelligently handles two types of Windows commands:

### Built-in Commands (run through `cmd /c`)

Commands like `dir`, `type`, `cd` are **built into cmd.exe** and need to be run through it:

- `cmd /c dir` - List files
- `cmd /c type file.txt` - Read file
- `cmd /c cd path` - Change directory

### External Executables (run directly)

Programs like `python.exe`, `git.exe` run directly:

- `python --version` - Direct execution
- `git status` - Direct execution

**Security:**

- ✅ No PowerShell (more controlled environment)
- ✅ No shell operators (`&&`, `|`, etc.) - blocked
- ✅ Commands validated against allowlist
- ✅ User confirmation required

## Windows Commands (Allowed)

### File & Directory Operations

```
dir [path]              List directory contents
dir /s                  List subdirectories recursively
type filename           Display file contents (like 'cat')
cd path                 Change directory
cd ..                   Go up one directory
tree                    Display directory tree
more filename           Page through file
```

### System Information

```
ver                     Windows version
systeminfo              Detailed system information
hostname                Computer name
whoami                  Current username
tasklist                List running processes
```

### File Search & Text Processing

```
where command           Find command location (like 'which')
find "text" file        Search for text in file
findstr pattern file    Advanced text search (like 'grep')
sort filename           Sort file contents
```

### Cross-Platform Development Tools

```
python --version        Python version
pip list                List Python packages
node --version          Node.js version
npm list                List npm packages
git status              Git repository status
docker ps               List Docker containers
```

## Unix Commands (Also Available)

Some Unix commands work on Windows if you have Git Bash or similar:

```
ls                      List files (if Git Bash installed)
cat                     Read file (if available)
pwd                     Print working directory
```

## Common Tasks

### List files in current directory

```
You: Show me the files here
Assistant: [calls] dir
```

### Read a file

```
You: Show me the contents of README.md
Assistant: [calls] type README.md
```

### Check Python version

```
You: What Python version am I using?
Assistant: [calls] python --version
```

### Navigate directories

```
You: Go to the parent directory
Assistant: [calls] cd ..

You: Go to C:\Users\matti
Assistant: [calls] cd C:\Users\matti
```

### Find a command

```
You: Where is git installed?
Assistant: [calls] where git
```

### See running processes

```
You: What processes are running?
Assistant: [calls] tasklist
```

## What's NOT Allowed (Security)

These are blocked for safety:

```
❌ del, erase          Delete files
❌ rmdir               Remove directories
❌ format              Format drives
❌ reg                 Registry editing
❌ powershell          PowerShell execution
❌ cmd                 Command prompt spawning
❌ && || | > <         Shell operators
```

## Adding More Commands

Edit `agent/tools.py` to add commands to the allowlist:

```python
WINDOWS_COMMANDS = {
    'dir', 'type', 'echo', 'cd', 'where', 'whoami',
    'tree', 'more', 'find', 'findstr', 'sort',
    'tasklist', 'systeminfo', 'hostname', 'ver',
    'your_command'  # Add here
}
```

## Platform Detection

Alice automatically detects that you're on Windows and:

- ✅ Shows "Platform: Windows" at startup
- ✅ Suggests Windows commands in responses
- ✅ Accepts both Windows and Unix commands (if available)

## Example Session

```
╔════════════════════════════════════════════╗
║     🧠 Local LLM Assistant (Alice)        ║
╚════════════════════════════════════════════╝

Platform: Windows
Working Directory: c:\Users\matti\projects\Alice
Shell: Direct execution (no PowerShell/bash)

You [Alice]: what files are in this directory?
Assistant: Let me check that for you.

💻 Tool call: execute_command
   Command: dir
   Execute this command? (y/n): y
   Executing...

   📤 Output:
   Volume in drive C is Windows
   Directory of c:\Users\matti\projects\Alice

   21/10/2025  23:10    <DIR>          .
   21/10/2025  23:10    <DIR>          ..
   21/10/2025  23:10    <DIR>          agent
   21/10/2025  23:10             1,234 app.py
   21/10/2025  23:10             5,678 README.md
   ...

You [Alice]: thanks!
Assistant: You're welcome! Is there anything else I can help you with?
```

## Tips

1. **Use Windows-native commands** when possible (`dir` instead of `ls`)
2. **Paths with spaces** need quotes: `cd "C:\Program Files"`
3. **Backslashes** work fine: `cd C:\Users\matti`
4. **Forward slashes** also work: `cd C:/Users/matti`
5. **Home directory**: Use `cd %USERPROFILE%` or just `cd ~`

Enjoy your Windows-friendly AI assistant! 🪟✨
