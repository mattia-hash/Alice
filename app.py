#!/usr/bin/env python3
"""
Local LLM Assistant - Main Application
A streaming chat interface with command execution capabilities.
"""

import os
import sys
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv

from agent.llm import LLMClient
from agent.memory import Memory
from agent.tools import CommandExecutor, get_tool_schemas, execute_tool_call


# Color codes for terminal output
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'
    DIM = '\033[2m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_colored(text: str, color: str = Colors.RESET):
    """Print colored text to terminal."""
    print(f"{color}{text}{Colors.RESET}")


class ThinkingFilter:
    """Filter and format <think> tags from LLM output."""
    
    def __init__(self, show_thinking: bool = False):
        """
        Initialize the thinking filter.
        
        Args:
            show_thinking: If True, show thinking in gray/dim. If False, hide completely.
        """
        self.show_thinking = show_thinking
        self.in_thinking = False
        self.thinking_buffer = []
    
    def process_chunk(self, chunk: str) -> str:
        """
        Process a streaming chunk and handle <think> tags.
        
        Returns:
            Filtered/formatted chunk to display
        """
        result = []
        i = 0
        
        while i < len(chunk):
            # Check for <think> opening tag
            if chunk[i:i+7] == '<think>':
                self.in_thinking = True
                self.thinking_buffer = []
                if self.show_thinking:
                    result.append(f"{Colors.GRAY}{Colors.DIM}[thinking: ")
                i += 7
                continue
            
            # Check for </think> closing tag
            if chunk[i:i+8] == '</think>':
                self.in_thinking = False
                if self.show_thinking:
                    result.append(f"]{Colors.RESET}")
                self.thinking_buffer = []
                i += 8
                continue
            
            # If we're inside thinking tags
            if self.in_thinking:
                if self.show_thinking:
                    result.append(chunk[i])
                # else: skip the character (hide thinking)
            else:
                # Normal text, output as-is
                result.append(chunk[i])
            
            i += 1
        
        return ''.join(result)
    
    def finalize(self) -> str:
        """Call at end of stream to close any unclosed tags."""
        if self.in_thinking and self.show_thinking:
            return f"]{Colors.RESET}"
        return ""


def get_user_confirmation(prompt: str) -> bool:
    """Ask user for yes/no confirmation."""
    while True:
        response = input(f"{prompt} (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Please answer 'y' or 'n'")


def main():
    """Main chat loop."""
    # Load environment variables
    load_dotenv()
    
    llm_url = os.getenv('LLM_COMPLETIONS_URL')
    model_name = os.getenv('MODEL_NAME', 'qwen2.5:3b')
    
    # Detect platform for context
    import platform
    os_name = platform.system()
    
    # Build platform-aware system prompt
    default_system_prompt = (
        f"You are a helpful AI assistant running on {os_name}. "
        "You have access to tools that can execute commands. "
        "When the user asks you to run commands, use the execute_command tool. "
    )
    
    if os_name == "Windows":
        default_system_prompt += (
            "Use Windows commands like 'dir' (list files), 'type' (read file), 'cd' (change directory), "
            "'where' (find command), 'tree' (directory tree). "
        )
    else:
        default_system_prompt += (
            "Use Unix commands like 'ls' (list files), 'cat' (read file), 'cd' (change directory), "
            "'which' (find command), 'pwd' (current directory). "
        )
    
    default_system_prompt += "Respond naturally in conversation."
    
    system_prompt = os.getenv('SYSTEM_PROMPT', default_system_prompt)
    
    if not llm_url:
        print_colored("❌ Error: LLM_COMPLETIONS_URL not set in .env file", Colors.RED)
        sys.exit(1)
    
    # Initialize components
    llm = LLMClient(llm_url, model_name, system_prompt)
    memory = Memory()
    executor = CommandExecutor(cwd=os.getcwd())
    tools = get_tool_schemas()
    
    # Create session ID
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # Check if we should use function calling
    use_function_calling = os.getenv('USE_FUNCTION_CALLING', 'true').lower() == 'true'
    
    print_colored("╔════════════════════════════════════════════╗", Colors.CYAN)
    print_colored("║     🧠 Local LLM Assistant (Alice)        ║", Colors.CYAN)
    print_colored("╚════════════════════════════════════════════╝", Colors.CYAN)
    print_colored(f"\nPlatform: {os_name}", Colors.BLUE)
    print_colored(f"Model: {model_name}", Colors.BLUE)
    print_colored(f"Endpoint: {llm_url}", Colors.BLUE)
    print_colored(f"Session: {session_id}", Colors.BLUE)
    print_colored(f"Working Directory: {executor.cwd}", Colors.BLUE)
    print_colored(f"Function Calling: {'Enabled' if use_function_calling else 'Disabled'}", Colors.BLUE)
    print_colored(f"Shell: Direct execution (no PowerShell/bash)", Colors.BLUE)
    print_colored("\nType 'exit', 'quit', or 'bye' to end the conversation.", Colors.YELLOW)
    print_colored("Type 'clear' to clear conversation history.\n", Colors.YELLOW)
    
    # Conversation history
    messages = []
    
    try:
        while True:
            # Get user input
            try:
                # Show current directory in prompt
                cwd_short = os.path.basename(executor.cwd) or executor.cwd
                user_input = input(f"{Colors.GREEN}You [{cwd_short}]: {Colors.RESET}").strip()
            except EOFError:
                break
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print_colored("\n👋 Goodbye!", Colors.CYAN)
                break
            
            if user_input.lower() == 'clear':
                messages = []
                print_colored("✨ Conversation history cleared.", Colors.YELLOW)
                continue
            
            # Add user message to history and database
            messages.append({'role': 'user', 'content': user_input})
            memory.add_message(session_id, 'user', user_input)
            
            # Agent loop: may need multiple iterations if tools are called
            max_iterations = 5
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                try:
                    # Call LLM with tools (if enabled)
                    response = llm.chat(messages, tools=tools if use_function_calling else None)
                    
                    # Check if we have tool calls
                    tool_calls = response.get('tool_calls', [])
                    content = response.get('content', '')
                    
                    # Display any text content (but not on first iteration if there are tool calls)
                    if content and content.strip():
                        # Show content before or after tool execution
                        if not tool_calls or iteration > 1:
                            print(f"{Colors.BLUE}Assistant: {Colors.RESET}", end='')
                            
                            # Filter thinking tags
                            show_thinking = os.getenv('SHOW_THINKING', 'false').lower() == 'true'
                            thinking_filter = ThinkingFilter(show_thinking=show_thinking)
                            filtered_content = thinking_filter.process_chunk(content)
                            filtered_content += thinking_filter.finalize()
                            
                            print(filtered_content)
                        
                        # Add to history
                        messages.append({'role': 'assistant', 'content': content})
                        memory.add_message(session_id, 'assistant', content)
                    
                    # If no tool calls, we're done
                    if not tool_calls:
                        break
                    
                    # Process tool calls
                    tool_results = []
                    for tool_call in tool_calls:
                        # Extract tool info
                        if isinstance(tool_call, dict):
                            tool_id = tool_call.get('id', 'unknown')
                            tool_name = tool_call.get('function', {}).get('name', '')
                            tool_args_str = tool_call.get('function', {}).get('arguments', '{}')
                            
                            try:
                                tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                            except json.JSONDecodeError:
                                tool_args = {}
                            
                            # Handle execute_command tool
                            if tool_name == 'execute_command':
                                command = tool_args.get('command', '')
                                args = tool_args.get('args', [])
                                
                                # Show proposed command
                                full_command = f"{command} {' '.join(args)}"
                                print_colored(f"\n💻 Tool call: execute_command", Colors.YELLOW)
                                print_colored(f"   Command: {full_command}", Colors.YELLOW)
                                
                                # Check safety
                                is_safe, error_msg = executor.is_command_safe(command, args)
                                if not is_safe:
                                    print_colored(f"   ⚠️  Safety check failed: {error_msg}", Colors.RED)
                                    result_msg = f"Error: {error_msg}"
                                    memory.add_command(session_id, command, args, approved=False)
                                else:
                                    # Ask for confirmation
                                    if get_user_confirmation("   Execute this command?"):
                                        print_colored("   Executing...", Colors.CYAN)
                                        result = execute_tool_call(tool_name, tool_args)
                                        
                                        # Log to database
                                        memory.add_command(
                                            session_id, command, args, approved=True,
                                            exit_code=result.get('exit_code'),
                                            stdout=result.get('stdout'),
                                            stderr=result.get('stderr')
                                        )
                                        
                                        # Update working directory if changed
                                        if result.get('cwd') and result['cwd'] != executor.cwd:
                                            executor.cwd = result['cwd']
                                            print_colored(f"\n   📁 Working directory: {executor.cwd}", Colors.CYAN)
                                        
                                        # Format result
                                        if result.get('success'):
                                            output = result.get('stdout', '').strip()
                                            if output:
                                                print_colored(f"\n   📤 Output:\n{output}", Colors.GREEN)
                                            result_msg = f"Success: {output}"
                                        else:
                                            error = result.get('stderr', '').strip()
                                            print_colored(f"\n   ❌ Error:\n{error}", Colors.RED)
                                            result_msg = f"Failed: {error}"
                                    else:
                                        result_msg = "Command execution cancelled by user"
                                        print_colored(f"   {result_msg}", Colors.YELLOW)
                                        memory.add_command(session_id, command, args, approved=False)
                                
                                # Add tool result
                                tool_results.append({
                                    'tool_call_id': tool_id,
                                    'role': 'tool',
                                    'name': tool_name,
                                    'content': result_msg
                                })
                    
                    # If we executed tools, just log them and finish
                    if tool_results:
                        # Log tool results to database
                        for result in tool_results:
                            memory.add_message(session_id, 'system', f"Tool {result['name']}: {result['content']}")
                        
                        # Don't call LLM again - just finish and return to prompt
                        # The command output was already shown to the user
                        break  # Done with this turn
                    
                    break  # No tool calls, exit loop
                    
                except KeyboardInterrupt:
                    print_colored("\n\n⚠️  Response interrupted", Colors.YELLOW)
                    break
                except Exception as e:
                    print_colored(f"\n❌ Error: {str(e)}", Colors.RED)
                    import traceback
                    traceback.print_exc()
                    break
            
            print()  # Empty line between exchanges
            
    except KeyboardInterrupt:
        print_colored("\n\n👋 Interrupted. Goodbye!", Colors.CYAN)
    finally:
        memory.close()


if __name__ == "__main__":
    main()

