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
from .tool_schemas import get_llm_tool_schemas


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
        print_colored("Type 'clear' to clear conversation history.", Colors.YELLOW)
        print_colored("Add '/tool' to your message to enable tool usage for that request.\n", Colors.YELLOW)

    def _clear_last_lines(self, num_lines: int) -> None:
        if num_lines <= 0:
            return
        for _ in range(num_lines):
            # Move cursor up and clear the line
            print("\033[F\033[K", end='')
        sys.stdout.flush()

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

                # Check if user wants to enable tools for this request
                enable_tools = '/tool' in user_input.lower()
                
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
                            # Stream assistant text while exposing tools so model knows about them
                            # Only pass tools if user requested it with /tool
                            tools_to_use = get_llm_tool_schemas() if enable_tools else None
                            if enable_tools:
                                print_colored("🛠️  Tool mode enabled for this request", Colors.CYAN)
                            
                            print(f"{Colors.BLUE}Alice: {Colors.RESET}", end='')
                            thinking_filter = ThinkingFilter(show_thinking=self.config.show_thinking)
                            streamed_chunks: List[str] = []
                            displayed_lines = 1  # includes the label line
                            for chunk in self.llm.stream_chat(messages, temperature=0.7, tools=tools_to_use):
                                filtered = thinking_filter.process_chunk(chunk)
                                if filtered:
                                    print(filtered, end='')
                                    sys.stdout.flush()
                                    displayed_lines += filtered.count('\n')
                                streamed_chunks.append(chunk)
                            tail = thinking_filter.finalize()
                            if tail:
                                print(tail, end='')
                            print()
                            content_streamed = ''.join(streamed_chunks)
                            displayed_lines += 1  # account for newline
                            
                            logger.debug(f"Streamed content length: {len(content_streamed)}")
                            logger.debug(f"Streamed content: {content_streamed[:200]}")

                            # After streaming, check for formal tool calls using a non-streaming request
                            # Only pass tools if user requested it with /tool
                            response = self.llm.chat(messages, tools=tools_to_use)
                            tool_calls = response.get('tool_calls', [])
                            content_full = response.get('content', '')
                            
                            logger.debug(f"Non-streaming content: {content_full[:200]}")
                            logger.debug(f"Tool calls: {len(tool_calls)}")

                            if tool_calls:
                                # Clear streamed text and run tool flow
                                self._clear_last_lines(displayed_lines)

                                if content_full and content_full.strip():
                                    messages.append({'role': 'assistant', 'content': content_full})
                                    self.memory.add_message(self.config.session_id, 'assistant', content_full)

                                tool_results = []
                                for tool_call in tool_calls:
                                    # Handle both ollama ToolCall objects and dict format
                                    if hasattr(tool_call, 'function'):
                                        # Ollama ToolCall object
                                        tool_id = 'unknown'
                                        function = tool_call.function
                                        tool_name = function.name if hasattr(function, 'name') else ''
                                        tool_args = function.arguments if hasattr(function, 'arguments') else {}
                                    elif isinstance(tool_call, dict):
                                        # Dictionary format (OpenAI style)
                                        tool_id = tool_call.get('id', 'unknown')
                                        tool_name = tool_call.get('function', {}).get('name', '')
                                        tool_args_str = tool_call.get('function', {}).get('arguments', '{}')
                                        try:
                                            tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                                        except json.JSONDecodeError:
                                            tool_args = {}
                                    else:
                                        continue

                                    if tool_name == 'execute_command':
                                        # With the simplified schema, only a single 'command' string is provided
                                        full_cmd_str = (tool_args.get('command') or '').strip()
                                        print_colored(f"\n💻 Tool call: execute_command", Colors.YELLOW)
                                        print_colored(f"   Command: {full_cmd_str}", Colors.YELLOW)

                                        # Parse for safety check
                                        try:
                                            import shlex, os as _os
                                            parts = shlex.split(full_cmd_str, posix=(_os.name != 'nt'))
                                        except Exception:
                                            parts = full_cmd_str.split()
                                        base_cmd = parts[0] if parts else ''
                                        base_args = parts[1:] if len(parts) > 1 else []

                                        is_safe, error_msg = self.executor.is_command_safe(base_cmd, base_args)
                                        if not is_safe:
                                            print_colored(f"   ⚠️  Safety check failed: {error_msg}", Colors.RED)
                                            result_msg = f"Error: {error_msg}"
                                            self.memory.add_command(self.config.session_id, base_cmd, base_args, approved=False)
                                        else:
                                            if get_user_confirmation("   Execute this command?"):
                                                print_colored("   Executing...", Colors.CYAN)
                                                result = execute_tool_call(tool_name, {'command': full_cmd_str})
                                                self.memory.add_command(
                                                    self.config.session_id, base_cmd, base_args, approved=True,
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
                                                self.memory.add_command(self.config.session_id, base_cmd, base_args, approved=False)
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
                                # No tool calls; commit streamed content
                                messages.append({'role': 'assistant', 'content': content_streamed})
                                self.memory.add_message(self.config.session_id, 'assistant', content_streamed)
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
