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


def print_colored(text: str, color: str = Colors.RESET) -> None:
    print(f"{color}{text}{Colors.RESET}")


def get_user_confirmation(prompt: str) -> bool:
    """Ask user for yes/no confirmation in the console."""
    while True:
        try:
            response = input(f"{prompt} (y/n): ").strip().lower()
        except EOFError:
            return False
        if response in ["y", "yes"]:
            return True
        if response in ["n", "no"]:
            return False
        print("Please answer 'y' or 'n'")
