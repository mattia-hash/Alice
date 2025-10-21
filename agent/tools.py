"""
Safe terminal command execution tools.
LangGraph-ready tool definitions with allowlist-based security.
"""

import subprocess
from typing import List, Dict, Optional, Tuple


class CommandExecutor:
    """Safe command executor with allowlist-based security."""
    
    # Allowlist of safe commands (expandable)
    ALLOWED_COMMANDS = {
        'ls', 'cat', 'pwd', 'echo', 'date', 'whoami',
        'git', 'docker', 'ps', 'df', 'du', 'find',
        'grep', 'head', 'tail', 'wc', 'which', 'uname',
        'python', 'pip', 'node', 'npm', 'cargo'
    }
    
    # Dangerous patterns to reject
    BLOCKED_PATTERNS = ['&&', '||', '|', '>', '<', ';', '`', '$', '$(']
    
    def __init__(self, timeout: int = 30, max_output_size: int = 10000):
        """
        Initialize command executor.
        
        Args:
            timeout: Maximum execution time in seconds
            max_output_size: Maximum output size to capture (in bytes)
        """
        self.timeout = timeout
        self.max_output_size = max_output_size
    
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
            Dict with keys: success, exit_code, stdout, stderr, error
        """
        # Safety check
        is_safe, error_msg = self.is_command_safe(command, args)
        if not is_safe:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': error_msg,
                'error': error_msg
            }
        
        try:
            # Execute command
            result = subprocess.run(
                [command] + args,
                capture_output=True,
                text=True,
                timeout=self.timeout
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
                'error': None
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': f'Command timed out after {self.timeout} seconds',
                'error': 'Timeout'
            }
        except FileNotFoundError:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': f"Command '{command}' not found",
                'error': 'Command not found'
            }
        except Exception as e:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': str(e),
                'error': str(e)
            }


# LangGraph-compatible tool function
def execute_command(command: str, args: List[str]) -> Dict:
    """
    LangGraph-compatible tool function for command execution.
    
    Args:
        command: The command to execute
        args: List of command arguments
        
    Returns:
        Execution result dictionary
    """
    executor = CommandExecutor()
    return executor.execute(command, args)

