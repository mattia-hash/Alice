import os
import sys
import math
import json
import logging
import traceback
from typing import List, Dict

from agent.tools import execute_tool_call
from .console import Colors, print_colored, get_user_confirmation
from .thinking import ThinkingFilter
from .parsing import extract_command_from_text


logger = logging.getLogger(__name__)


class ChatSession:
    def __init__(self, llm, memory, executor, tools: List[Dict], config) -> None:
        self.llm = llm
        self.memory = memory
        self.executor = executor
        self.tools = tools
        self.config = config

    def _print_header(self) -> None:
        print_colored("╔════════════════════════════════════════════╗", Colors.CYAN)
        print_colored("║     🧠 Local LLM Assistant (Alice)        ║", Colors.CYAN)
        print_colored("╚════════════════════════════════════════════╝", Colors.CYAN)
        print_colored(f"\nPlatform: {self.config.os_name}", Colors.BLUE)
        print_colored(f"Model: {self.config.model_name}", Colors.BLUE)
        print_colored(f"Endpoint: {self.llm.base_url}", Colors.BLUE)
        print_colored(f"Session: {self.config.session_id}", Colors.BLUE)
        print_colored(f"Working Directory: {self.executor.cwd}", Colors.BLUE)
        print_colored(f"Function Calling: {'Enabled' if self.config.use_function_calling else 'Disabled'}", Colors.BLUE)
        if self.config.max_context_tokens:
            print_colored(f"Approx Context Window (max): {self.config.max_context_tokens} tokens", Colors.BLUE)
        print_colored(f"Shell: Direct execution (no PowerShell/bash)", Colors.BLUE)
        print_colored("\nType 'exit', 'quit', or 'bye' to end the conversation.", Colors.YELLOW)
        print_colored("Type 'clear' to clear conversation history.\n", Colors.YELLOW)

    def run(self) -> None:
        self._print_header()
        messages: List[Dict[str, str]] = []

        try:
            while True:
                try:
                    cwd_short = os.path.basename(self.executor.cwd) or self.executor.cwd
                    user_input = input(f"{Colors.GREEN}Mattia [{cwd_short}]: {Colors.RESET}").strip()
                except EOFError:
                    break

                if not user_input:
                    continue
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print_colored("\n👋 Goodbye!", Colors.CYAN)
                    break
                if user_input.lower() == 'clear':
                    messages = []
                    print_colored("✨ Conversation history cleared.", Colors.YELLOW)
                    continue

                messages.append({'role': 'user', 'content': user_input})
                self.memory.add_message(self.config.session_id, 'user', user_input)

                try:
                    total_chars = sum(len(m.get('content', '')) for m in messages)
                    approx_tokens = math.ceil(total_chars / 4)
                    if self.config.max_context_tokens:
                        logger.info(f"Context usage ~{approx_tokens} tokens ({total_chars} chars) of {self.config.max_context_tokens}")
                        print_colored(f"≈ Context: {approx_tokens}/{self.config.max_context_tokens} tokens", Colors.GRAY)
                    else:
                        logger.info(f"Context usage ~{approx_tokens} tokens ({total_chars} chars)")
                        print_colored(f"≈ Context: ~{approx_tokens} tokens", Colors.GRAY)
                except Exception:
                    pass

                max_iterations = 5
                iteration = 0

                while iteration < max_iterations:
                    iteration += 1
                    try:
                        if self.config.use_function_calling:
                            response = self.llm.chat(messages, tools=self.tools)
                            tool_calls = response.get('tool_calls', [])
                            content = response.get('content', '')

                            if content and content.strip():
                                if not tool_calls or iteration > 1:
                                    print(f"{Colors.BLUE}Alice: {Colors.RESET}", end='')
                                    thinking_filter = ThinkingFilter(show_thinking=self.config.show_thinking)
                                    filtered_content = thinking_filter.process_chunk(content)
                                    filtered_content += thinking_filter.finalize()
                                    print(filtered_content)
                                messages.append({'role': 'assistant', 'content': content})
                                self.memory.add_message(self.config.session_id, 'assistant', content)

                            if not tool_calls:
                                break

                            tool_results = []
                            for tool_call in tool_calls:
                                if isinstance(tool_call, dict):
                                    tool_id = tool_call.get('id', 'unknown')
                                    tool_name = tool_call.get('function', {}).get('name', '')
                                    tool_args_str = tool_call.get('function', {}).get('arguments', '{}')
                                    try:
                                        tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                                    except json.JSONDecodeError:
                                        tool_args = {}

                                    if tool_name == 'execute_command':
                                        command = tool_args.get('command', '')
                                        args = tool_args.get('args', [])
                                        full_command = f"{command} {' '.join(args)}".strip()
                                        print_colored(f"\n💻 Tool call: execute_command", Colors.YELLOW)
                                        print_colored(f"   Command: {full_command}", Colors.YELLOW)

                                        is_safe, error_msg = self.executor.is_command_safe(command, args)
                                        if not is_safe:
                                            print_colored(f"   ⚠️  Safety check failed: {error_msg}", Colors.RED)
                                            result_msg = f"Error: {error_msg}"
                                            self.memory.add_command(self.config.session_id, command, args, approved=False)
                                        else:
                                            if get_user_confirmation("   Execute this command?"):
                                                print_colored("   Executing...", Colors.CYAN)
                                                result = execute_tool_call(tool_name, tool_args)
                                                self.memory.add_command(
                                                    self.config.session_id, command, args, approved=True,
                                                    exit_code=result.get('exit_code'),
                                                    stdout=result.get('stdout'),
                                                    stderr=result.get('stderr')
                                                )
                                                if result.get('cwd') and result['cwd'] != self.executor.cwd:
                                                    self.executor.cwd = result['cwd']
                                                    print_colored(f"\n   📁 Working directory: {self.executor.cwd}", Colors.CYAN)
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
                                                self.memory.add_command(self.config.session_id, command, args, approved=False)
                                        tool_results.append({
                                            'tool_call_id': tool_id,
                                            'role': 'tool',
                                            'name': tool_name,
                                            'content': result_msg
                                        })

                            if tool_results:
                                for result in tool_results:
                                    self.memory.add_message(self.config.session_id, 'system', f"Tool {result['name']}: {result['content']}")
                                break
                        else:
                            print(f"{Colors.BLUE}Alice: {Colors.RESET}", end='')
                            thinking_filter = ThinkingFilter(show_thinking=self.config.show_thinking)
                            full_content_parts: List[str] = []
                            for chunk in self.llm.stream_chat(messages, temperature=0.7, tools=None):
                                filtered = thinking_filter.process_chunk(chunk)
                                if filtered:
                                    print(filtered, end='')
                                    sys.stdout.flush()
                                full_content_parts.append(chunk)
                            tail = thinking_filter.finalize()
                            if tail:
                                print(tail, end='')
                            print()
                            content = ''.join(full_content_parts)
                            messages.append({'role': 'assistant', 'content': content})
                            self.memory.add_message(self.config.session_id, 'assistant', content)

                            action = self.llm.parse_action(content)
                            command = None
                            args = []
                            if isinstance(action, dict) and action.get('action') in ('run_command', 'execute_command'):
                                command = action.get('command')
                                args = action.get('args', []) if isinstance(action.get('args'), list) else []
                            else:
                                cmd2, args2 = extract_command_from_text(content)
                                if cmd2:
                                    command, args = cmd2, args2

                            if command:
                                full_command = f"{command} {' '.join(args)}".strip()
                                print_colored(f"\n💻 Tool call: execute_command", Colors.YELLOW)
                                print_colored(f"   Command: {full_command}", Colors.YELLOW)
                                is_safe, error_msg = self.executor.is_command_safe(command, args)
                                if not is_safe:
                                    print_colored(f"   ⚠️  Safety check failed: {error_msg}", Colors.RED)
                                    self.memory.add_command(self.config.session_id, command, args, approved=False)
                                else:
                                    if get_user_confirmation("   Execute this command?"):
                                        print_colored("   Executing...", Colors.CYAN)
                                        result = self.executor.execute(command, args)
                                        self.memory.add_command(
                                            self.config.session_id, command, args, approved=True,
                                            exit_code=result.get('exit_code'),
                                            stdout=result.get('stdout'),
                                            stderr=result.get('stderr')
                                        )
                                        if result.get('cwd') and result['cwd'] != self.executor.cwd:
                                            self.executor.cwd = result['cwd']
                                            print_colored(f"\n   📁 Working directory: {self.executor.cwd}", Colors.CYAN)
                                        if result.get('success'):
                                            output = result.get('stdout', '').strip()
                                            if output:
                                                print_colored(f"\n   📤 Output:\n{output}", Colors.GREEN)
                                        else:
                                            error = result.get('stderr', '').strip()
                                            print_colored(f"\n   ❌ Error:\n{error}", Colors.RED)

                            break

                    except KeyboardInterrupt:
                        print_colored("\n\n⚠️  Response interrupted", Colors.YELLOW)
                        break
                    except Exception as e:
                        print_colored(f"\n❌ Error: {str(e)}", Colors.RED)
                        traceback.print_exc()
                        break

                print()
        except KeyboardInterrupt:
            print_colored("\n\n👋 Interrupted. Goodbye!", Colors.CYAN)
        finally:
            self.memory.close()
