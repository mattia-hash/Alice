import os
import logging
import platform
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv


@dataclass
class Config:
    llm_url: str
    model_name: str
    username: Optional[str]
    password: Optional[str]
    log_level_str: str
    os_name: str
    system_prompt: str
    use_function_calling: bool
    show_thinking: bool
    context_length_env: Optional[int]
    max_context_tokens: Optional[int]
    session_id: str


def setup_logging(log_level_str: str) -> None:
    level = getattr(logging, log_level_str.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True,
    )


def _parse_int_env(name: str) -> Optional[int]:
    try:
        value = os.getenv(name)
        if value is None:
            return None
        return int(value.strip())
    except ValueError:
        return None


def build_system_prompt(os_name: str) -> str:
    prompt = (
        f"You are Alice, a helpful AI assistant running on {os_name}. "
        "You are assisting Mattia. "
        "Your PRIMARY mode is normal conversation - respond naturally and helpfully.\n\n"
        "IMPORTANT: You have access to a command execution tool, but you should RARELY use it. "
        "Default to conversational responses. ONLY call execute_command when the user "
        "EXPLICITLY and CLEARLY requests a system command or file operation.\n\n"
        "Examples of when TO use execute_command:\n"
        "- User: \"list the files here\" or \"show me what's in this directory\"\n"
        "- User: \"run dir\" or \"execute ls -la\"\n"
        "- User: \"check git status\" or \"what's my current directory\"\n\n"
        "Examples of when NOT to use execute_command (respond conversationally instead):\n"
        "- User: \"hello\" → Just greet them back\n"
        "- User: \"how are you?\" → Respond naturally\n"
        "- User: \"what can you do?\" → Explain your capabilities in text\n"
        "- User: \"tell me about Python\" → Provide information conversationally\n\n"
        "CRITICAL: If there's ANY doubt, respond with text ONLY. Don't use tools unless absolutely necessary."
    )
    return prompt


def load_config() -> Config:
    load_dotenv()

    log_level_str = os.getenv('LOGGING_LEVEL', 'INFO').upper()
    if log_level_str.startswith('LOGGING.'):
        log_level_str = log_level_str.replace('LOGGING.', '')

    llm_url = os.getenv('LLM_COMPLETIONS_URL') or ''
    model_name = os.getenv('MODEL_NAME', 'qwen2.5:3b')
    username = os.getenv('USERNAME')
    password = os.getenv('PASSWORD')

    max_context_tokens = _parse_int_env('MODEL_CONTEXT_MAX')
    if not max_context_tokens:
        max_context_tokens = _parse_int_env('CONTEXT_LENGTH')

    context_length_env = _parse_int_env('CONTEXT_LENGTH')

    os_name = platform.system()
    default_system_prompt = build_system_prompt(os_name)
    system_prompt = os.getenv('SYSTEM_PROMPT', default_system_prompt)

    use_function_calling = os.getenv('USE_FUNCTION_CALLING', 'true').lower() == 'true'
    show_thinking = os.getenv('SHOW_THINKING', 'false').lower() == 'true'

    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    return Config(
        llm_url=llm_url,
        model_name=model_name,
        username=username,
        password=password,
        log_level_str=log_level_str,
        os_name=os_name,
        system_prompt=system_prompt,
        use_function_calling=use_function_calling,
        show_thinking=show_thinking,
        context_length_env=context_length_env,
        max_context_tokens=max_context_tokens,
        session_id=session_id,
    )
