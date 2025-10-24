#!/usr/bin/env python3
"""
Local LLM Assistant - Main Application
A streaming chat interface with command execution capabilities.
"""

import os
import sys
import logging

from agent.llm import LLMClient
from agent.memory import Memory
from agent.tools import CommandExecutor, get_tool_schemas

from app_core.config import load_config, setup_logging
from app_core.session import ChatSession
from app_core.console import print_colored, Colors


def main():
    """Application entrypoint that wires up dependencies and runs the chat session."""
    config = load_config()

    # Ensure LLM URL present before proceeding
    if not config.llm_url:
        print_colored("❌ Error: LLM_COMPLETIONS_URL not set in .env file", Colors.RED)
        sys.exit(1)
    
    # Configure logging
    setup_logging(config.log_level_str)
    logger = logging.getLogger(__name__)
    logger.info(f"Logging level set to: {config.log_level_str}")

    # Initialize components
    logger.info(f"Initializing LLM client with URL: {config.llm_url}")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"Auth: {'Enabled' if config.username and config.password else 'Disabled'}")

    llm = LLMClient(
        config.llm_url,
        config.model_name,
        config.system_prompt,
        username=config.username,
        password=config.password,
        context_length=config.context_length_env,
    )
    memory = Memory()
    executor = CommandExecutor(cwd=os.getcwd())
    tools = get_tool_schemas()
    
    # Run session
    session = ChatSession(llm=llm, memory=memory, executor=executor, tools=tools, config=config)
    session.run()


if __name__ == "__main__":
    main()

