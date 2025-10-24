from .console import Colors


class ThinkingFilter:
    """Filter and format <think> tags from LLM output."""

    def __init__(self, show_thinking: bool = False):
        self.show_thinking = show_thinking
        self.in_thinking = False
        self.thinking_buffer = []

    def process_chunk(self, chunk: str) -> str:
        result = []
        i = 0
        while i < len(chunk):
            if chunk[i:i+7] == '<think>':
                self.in_thinking = True
                self.thinking_buffer = []
                if self.show_thinking:
                    result.append(f"{Colors.GRAY}{Colors.DIM}[thinking: ")
                i += 7
                continue
            if chunk[i:i+8] == '</think>':
                self.in_thinking = False
                if self.show_thinking:
                    result.append(f"]{Colors.RESET}")
                self.thinking_buffer = []
                i += 8
                continue
            if self.in_thinking:
                if self.show_thinking:
                    result.append(chunk[i])
            else:
                result.append(chunk[i])
            i += 1
        return ''.join(result)

    def finalize(self) -> str:
        if self.in_thinking and self.show_thinking:
            return f"]{Colors.RESET}"
        return ""
