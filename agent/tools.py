"""
Safe terminal command execution tools.
LangGraph-ready tool definitions with allowlist-based security.
"""

import subprocess
import json
import os
from typing import List, Dict, Optional, Tuple, Any
import shlex


class CommandExecutor:
    """
    Safe command executor with allowlist-based security.
    
    Uses subprocess.run() without shell=True for security.
    Commands run directly (not through PowerShell or bash).
    Works with both Windows (cmd.exe style) and Unix commands.
    """
    
    # Allowlist of safe commands (expandable)
    # Unix/Linux commands
    UNIX_COMMANDS = {
        'ls', 'cat', 'pwd', 'echo', 'date', 'whoami', 'cd',
        'git', 'docker', 'ps', 'df', 'du', 'find',
        'grep', 'head', 'tail', 'wc', 'which', 'uname'
    }
    
    # Windows built-in commands (require cmd.exe)
    WINDOWS_BUILTINS = {
        'dir', 'type', 'cd', 'echo', 'tree', 'more',
        'find', 'sort', 'ver', 'vol', 'path', 'set',
        'copy', 'move', 'ren', 'del', 'mkdir', 'rmdir'
    }
    
    # Windows external commands (executables)
    WINDOWS_EXECUTABLES = {
        'where', 'whoami', 'tasklist', 'systeminfo', 
        'hostname', 'findstr', 'fc'
    }
    
    # Cross-platform development tools
    DEV_TOOLS = {
        'python', 'pip', 'node', 'npm', 'cargo', 'rustc',
        'git', 'docker', 'code', 'java', 'javac', 'mvn', 'gradle'
    }
    
    # Combine all allowed commands
    ALLOWED_COMMANDS = UNIX_COMMANDS | WINDOWS_BUILTINS | WINDOWS_EXECUTABLES | DEV_TOOLS
    
    # Dangerous patterns to reject
    BLOCKED_PATTERNS = ['&&', '||', '|', '>', '<', ';', '`', '$', '$(']
    
    def __init__(self, timeout: int = 30, max_output_size: int = 10000, cwd: Optional[str] = None):
        """
        Initialize command executor.
        
        Args:
            timeout: Maximum execution time in seconds
            max_output_size: Maximum output size to capture (in bytes)
            cwd: Current working directory (defaults to current dir)
        """
        self.timeout = timeout
        self.max_output_size = max_output_size
        self.cwd = cwd or os.getcwd()
    
    def is_command_safe(self, command: str, args: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Check if a command is safe to execute.
        
        Returns:
            (is_safe, error_message)
        """
        # Check if command is in allowlist
        if command not in self.ALLOWED_COMMANDS:
            return False, f"Command '{command}' is not in the allowlist"
        
        # Check for dangerous patterns in command
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in command:
                return False, f"Command contains blocked pattern: {pattern}"
        
        # Check for dangerous patterns in arguments
        args_str = ' '.join(args)
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in args_str:
                return False, f"Arguments contain blocked pattern: {pattern}"
        
        return True, None
    
    def execute(self, command: str, args: List[str]) -> Dict:
        """
        Execute a command safely.
        
        Returns:
            Dict with keys: success, exit_code, stdout, stderr, error, cwd (current working directory)
        """
        # Safety check
        is_safe, error_msg = self.is_command_safe(command, args)
        if not is_safe:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': error_msg,
                'error': error_msg,
                'cwd': self.cwd
            }
        
        # Special handling for cd command
        if command == 'cd':
            new_dir = args[0] if args else os.path.expanduser('~')
            try:
                # Expand ~ and make absolute
                new_dir = os.path.abspath(os.path.expanduser(new_dir))
                
                if os.path.isdir(new_dir):
                    self.cwd = new_dir
                    return {
                        'success': True,
                        'exit_code': 0,
                        'stdout': f'Changed directory to: {self.cwd}',
                        'stderr': '',
                        'error': None,
                        'cwd': self.cwd
                    }
                else:
                    return {
                        'success': False,
                        'exit_code': 1,
                        'stdout': '',
                        'stderr': f'Directory not found: {new_dir}',
                        'error': 'Directory not found',
                        'cwd': self.cwd
                    }
            except Exception as e:
                return {
                    'success': False,
                    'exit_code': 1,
                    'stdout': '',
                    'stderr': str(e),
                    'error': str(e),
                    'cwd': self.cwd
                }
        
        try:
            # Check if this is a Windows built-in command
            # Built-ins need to be run through cmd.exe
            if command in self.WINDOWS_BUILTINS:
                # Use cmd /c to run built-in commands
                cmd_line = [command] + args
                result = subprocess.run(
                    ['cmd', '/c'] + cmd_line,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=self.cwd
                )
            else:
                # Execute external command directly
                result = subprocess.run(
                    [command] + args,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=self.cwd
                )
            
            # Truncate output if too large
            stdout = result.stdout[:self.max_output_size]
            stderr = result.stderr[:self.max_output_size]
            
            if len(result.stdout) > self.max_output_size:
                stdout += "\n... (output truncated)"
            if len(result.stderr) > self.max_output_size:
                stderr += "\n... (output truncated)"
            
            return {
                'success': result.returncode == 0,
                'exit_code': result.returncode,
                'stdout': stdout,
                'stderr': stderr,
                'error': None,
                'cwd': self.cwd
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': f'Command timed out after {self.timeout} seconds',
                'error': 'Timeout',
                'cwd': self.cwd
            }
        except FileNotFoundError:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': f"Command '{command}' not found",
                'error': 'Command not found',
                'cwd': self.cwd
            }
        except Exception as e:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': str(e),
                'error': str(e),
                'cwd': self.cwd
            }


# Tool function for ollama library (receives full command string)
def execute_command(command: str) -> Dict:
    """
    Execute a terminal command safely on Windows. The command will be shown to the user for confirmation before execution. Only commands in the allowlist are permitted (dir, type, cd, where, tree, echo, etc.).
    
    Args:
        command: Full command to execute, including arguments (e.g., 'dir /b' or 'type README.md')
        
    Returns:
        Execution result with success status, stdout, stderr, and exit code
    """
    if not command or not command.strip():
        return {
            "success": False, 
            "error": "No command provided", 
            "stdout": "", 
            "stderr": "", 
            "exit_code": -1,
            "cwd": os.getcwd()
        }
    
    # Parse into base command and args
    try:
        parts = shlex.split(command, posix=(os.name != 'nt'))
    except ValueError:
        # Fallback naive split
        parts = command.split()
    
    base_command = parts[0] if parts else ""
    args = parts[1:] if len(parts) > 1 else []
    
    executor = CommandExecutor()
    return executor.execute(base_command, args)


# For ollama library: Return actual callable functions instead of JSON schemas
def get_tool_functions() -> List:
    """Get list of actual callable tool functions for ollama."""
    return [execute_command]


# Legacy: Keep for backwards compatibility with schema-based approaches
def get_tool_schemas() -> List[Dict]:
    """
    Get tool schemas in OpenAI format (legacy).
    
    Note: When using the ollama library, use get_tool_functions() instead.
    This is kept for backwards compatibility only.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "execute_command",
                "description": "Execute a terminal command safely on Windows. The command will be shown to the user for confirmation before execution. Only commands in the allowlist are permitted (dir, type, cd, where, tree, echo, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Full command to execute, including arguments (e.g., 'dir /b' or 'type README.md')"
                        }
                    },
                    "required": ["command"]
                }
            }
        }
    ]


def execute_tool_call(tool_name: str, tool_args: Dict[str, Any]) -> Dict:
    """
    Execute a tool call by name with provided arguments.
    
    Args:
        tool_name: Name of the tool to execute
        tool_args: Dictionary of arguments for the tool
        
    Returns:
        Tool execution result
    """
    if tool_name == "execute_command":
        full_cmd = (tool_args.get("command") or "").strip()
        if not full_cmd:
            return {"success": False, "error": "No command provided"}
        # Call the updated execute_command that takes a full command string
        return execute_command(full_cmd)
    else:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }

