#!/usr/bin/env python3
"""
Local LLM Assistant - Main Application
A streaming chat interface with command execution capabilities.
"""

import os
import sys
import uuid
from datetime import datetime
from dotenv import load_dotenv

from agent.llm import LLMClient
from agent.memory import Memory
from agent.tools import CommandExecutor


# Color codes for terminal output
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_colored(text: str, color: str = Colors.RESET):
    """Print colored text to terminal."""
    print(f"{color}{text}{Colors.RESET}")


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


def handle_command_action(action: dict, executor: CommandExecutor, 
                          memory: Memory, session_id: str) -> str:
    """
    Handle a command execution action.
    
    Returns:
        Result message to show to user
    """
    command = action.get('command', '')
    args = action.get('args', [])
    
    if not command:
        return "[Error: No command specified]"
    
    # Show command to user
    full_command = f"{command} {' '.join(args)}"
    print_colored(f"\n💻 Proposed command: {full_command}", Colors.YELLOW)
    
    # Check if command is safe
    is_safe, error_msg = executor.is_command_safe(command, args)
    if not is_safe:
        print_colored(f"⚠️  Safety check failed: {error_msg}", Colors.RED)
        memory.add_command(session_id, command, args, approved=False)
        return f"[Command rejected: {error_msg}]"
    
    # Ask for confirmation
    if not get_user_confirmation("Execute this command?"):
        memory.add_command(session_id, command, args, approved=False)
        return "[Command execution cancelled by user]"
    
    # Execute command
    print_colored("Executing...", Colors.CYAN)
    result = executor.execute(command, args)
    
    # Log to database
    memory.add_command(
        session_id, command, args, approved=True,
        exit_code=result['exit_code'],
        stdout=result['stdout'],
        stderr=result['stderr']
    )
    
    # Format result
    if result['success']:
        output = result['stdout'].strip()
        if output:
            print_colored(f"\n📤 Output:\n{output}", Colors.GREEN)
        return f"[Command executed successfully]\n{output}"
    else:
        error = result['stderr'].strip()
        print_colored(f"\n❌ Error:\n{error}", Colors.RED)
        return f"[Command failed with exit code {result['exit_code']}]\n{error}"


def main():
    """Main chat loop."""
    # Load environment variables
    load_dotenv()
    
    llm_url = os.getenv('LLM_COMPLETIONS_URL')
    model_name = os.getenv('MODEL_NAME', 'qwen2.5:3b')
    system_prompt = os.getenv('SYSTEM_PROMPT', 
        "You are a helpful AI assistant. You can respond to questions and propose "
        "terminal commands when needed. When proposing a command, respond with JSON: "
        '{"action": "run_command", "command": "ls", "args": ["-la"]}. '
        "For normal responses, just respond naturally or use: "
        '{"action": "respond", "text": "your response"}.'
    )
    
    if not llm_url:
        print_colored("❌ Error: LLM_COMPLETIONS_URL not set in .env file", Colors.RED)
        sys.exit(1)
    
    # Initialize components
    llm = LLMClient(llm_url, model_name, system_prompt)
    memory = Memory()
    executor = CommandExecutor()
    
    # Create session ID
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # Print welcome message
    print_colored("╔════════════════════════════════════════════╗", Colors.CYAN)
    print_colored("║     🧠 Local LLM Assistant (Alice)        ║", Colors.CYAN)
    print_colored("╚════════════════════════════════════════════╝", Colors.CYAN)
    print_colored(f"\nModel: {model_name}", Colors.BLUE)
    print_colored(f"Endpoint: {llm_url}", Colors.BLUE)
    print_colored(f"Session: {session_id}", Colors.BLUE)
    print_colored("\nType 'exit', 'quit', or 'bye' to end the conversation.", Colors.YELLOW)
    print_colored("Type 'clear' to clear conversation history.\n", Colors.YELLOW)
    
    # Conversation history
    messages = []
    
    try:
        while True:
            # Get user input
            try:
                user_input = input(f"{Colors.GREEN}You: {Colors.RESET}").strip()
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
            
            # Get streaming response from LLM
            print(f"{Colors.BLUE}Assistant: {Colors.RESET}", end='', flush=True)
            
            response_chunks = []
            try:
                for chunk in llm.stream_chat(messages):
                    print(chunk, end='', flush=True)
                    response_chunks.append(chunk)
                print()  # New line after response
            except KeyboardInterrupt:
                print_colored("\n\n⚠️  Response interrupted", Colors.YELLOW)
                continue
            except Exception as e:
                print_colored(f"\n❌ Error: {str(e)}", Colors.RED)
                continue
            
            # Combine response
            full_response = ''.join(response_chunks)
            
            if not full_response.strip():
                print_colored("(No response received)", Colors.YELLOW)
                continue
            
            # Add assistant message to history and database
            messages.append({'role': 'assistant', 'content': full_response})
            memory.add_message(session_id, 'assistant', full_response)
            
            # Parse for actions (command execution)
            action = llm.parse_action(full_response)
            
            if action.get('action') == 'run_command':
                # Handle command execution
                result = handle_command_action(action, executor, memory, session_id)
                
                # Add command result to conversation context
                messages.append({'role': 'user', 'content': f"Command result: {result}"})
                memory.add_message(session_id, 'system', f"Command result: {result}")
            
            print()  # Empty line between exchanges
            
    except KeyboardInterrupt:
        print_colored("\n\n👋 Interrupted. Goodbye!", Colors.CYAN)
    finally:
        memory.close()


if __name__ == "__main__":
    main()

