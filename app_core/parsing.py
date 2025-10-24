import json
import re
from typing import List, Tuple, Optional


def extract_command_from_text(text: str) -> Tuple[Optional[str], Optional[List[str]]]:
    """Try to extract a proposed command from assistant text.
    Returns (command, args) or (None, None) if not found.
    Supports JSON action blocks and [execute_command: {...}] hints.
    """
    match = re.search(r"\[execute_command:\s*(\{[\s\S]*?\})\]", text)
    if match:
        raw = match.group(1)
        safe = raw.replace("'", '"')
        try:
            data = json.loads(safe)
            command = data.get('command')
            args = data.get('args', [])
            if isinstance(command, str) and isinstance(args, list):
                return command, [str(a) for a in args]
        except json.JSONDecodeError:
            pass

    match2 = re.search(r"execute_command\s*[:\(]\s*([\w.-]+)(.*?)[\)\].]?", text, re.IGNORECASE)
    if match2:
        command = match2.group(1)
        args_str = match2.group(2) or ''
        args = [a for a in re.findall(r"[^\s]+", args_str) if a not in {']', ')', '.'}]
        return command, args

    match3 = re.search(r"\bexecute_command\s+([\w.-]+)([^\n\r]*)", text, re.IGNORECASE)
    if match3:
        command = match3.group(1)
        args_str = (match3.group(2) or '').strip()
        args = [a for a in re.findall(r"[^\s]+", args_str) if a not in {']', ')', '.'}]
        return command, args

    return None, None
