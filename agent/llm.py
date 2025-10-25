"""
LLM interface using the ollama Python library.
Supports basic authentication for reverse proxy setups.
"""

import base64
import logging
import warnings
from typing import Iterator, Dict, List, Optional
from ollama import Client
import httpx

# Disable SSL warnings for self-signed certificates
warnings.filterwarnings('ignore', message='.*Unverified HTTPS request.*')
warnings.filterwarnings('ignore', message='.*verify=False.*')

logger = logging.getLogger(__name__)


class LLMClient:
    """Ollama client with basic auth support."""
    
    def __init__(self, base_url: str, model_name: str, system_prompt: Optional[str] = None,
                 username: Optional[str] = None, password: Optional[str] = None,
                 context_length: Optional[int] = None):
        """
        Initialize Ollama client.
        
        Args:
            base_url: API endpoint URL (e.g., http://your-server.com:11434/api/chat)
            model_name: Name of the model to use
            system_prompt: Optional system prompt
            username: Optional username for basic auth
            password: Optional password for basic auth
            context_length: Optional context window size
        """
        # Extract host from base_url (remove /api/chat or /api/generate paths)
        host = base_url.replace('/api/chat', '').replace('/api/generate', '').replace('/v1/chat/completions', '')
        
        # Setup basic auth headers if credentials provided
        headers = {}
        if username and password:
            credentials = f"{username}:{password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f'Basic {encoded}'
            logger.info("Basic auth enabled for Ollama client")
        
        # Initialize the ollama client with just host and headers
        # We'll configure SSL verification by monkey-patching after creation
        self.client = Client(
            host=host,
            headers=headers if headers else None
        )
        
        # Monkey-patch the httpx client to disable SSL verification
        # This is necessary for self-signed certificates
        if hasattr(self.client, '_client') and isinstance(self.client._client, httpx.Client):
            # Replace the existing client with one that has verify=False
            old_client = self.client._client
            self.client._client = httpx.Client(
                headers=headers if headers else None,
                verify=False,
                timeout=120.0,
                base_url=host
            )
            old_client.close()
            logger.info("SSL verification disabled via client patching")
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.context_length = context_length
        self.base_url = host  # Keep for logging compatibility
        
        logger.info(f"Ollama client initialized: {host}")
        logger.info("SSL verification disabled (self-signed certificate support)")
    
    def _build_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Build message list with optional system prompt."""
        if self.system_prompt and (not messages or messages[0]['role'] != 'system'):
            return [{'role': 'system', 'content': self.system_prompt}] + messages
        return messages
    
    def stream_chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, 
                    tools: Optional[List] = None) -> Iterator[str]:
        """
        Stream chat completion responses.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            tools: Optional list of callable functions for tool use
            
        Yields:
            Content chunks as they arrive
        """
        messages = self._build_messages(messages)
        
        # Build options
        options = {'temperature': temperature}
        if self.context_length:
            options['num_ctx'] = int(self.context_length)
        
        try:
            logger.debug(f"Streaming request to {self.model_name} with tools: {tools is not None}")
            
            # Stream with tools if provided
            stream = self.client.chat(
                model=self.model_name,
                messages=messages,
                tools=tools,
                options=options,
                stream=True
            )
            
            for chunk in stream:
                # Handle ChatResponse object - access as dict or object attributes
                if hasattr(chunk, 'message'):
                    # Object attribute access
                    message = chunk.message
                    if hasattr(message, 'content'):
                        content = message.content
                        if content:
                            yield content
                elif isinstance(chunk, dict):
                    # Dictionary access (fallback)
                    if 'message' in chunk and 'content' in chunk['message']:
                        content = chunk['message']['content']
                        if content:
                            yield content
                        
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            yield f"\n[Error: {str(e)}]"
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, 
             tools: Optional[List] = None) -> Dict:
        """
        Non-streaming chat completion (collects full response including tool calls).
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            tools: Optional list of callable functions
            
        Returns:
            Dict with 'content' (text) and 'tool_calls' (list)
        """
        messages = self._build_messages(messages)
        
        # Build options
        options = {'temperature': temperature}
        if self.context_length:
            options['num_ctx'] = int(self.context_length)
        
        try:
            logger.debug(f"Non-streaming request to {self.model_name}")
            logger.debug(f"Tools provided: {tools is not None}")
            
            # Call ollama with tools directly
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                tools=tools,
                options=options,
                stream=False
            )
            
            logger.debug(f"Response type: {type(response)}")
            
            # Parse response - ollama returns a ChatResponse object
            if hasattr(response, 'message'):
                # Object attribute access
                message = response.message
                content = getattr(message, 'content', '')
                tool_calls = getattr(message, 'tool_calls', []) or []
                if tool_calls:
                    logger.debug(f"Tool calls found: {len(tool_calls)}")
                return {
                    'content': content,
                    'tool_calls': tool_calls
                }
            elif isinstance(response, dict):
                # Dictionary access (fallback)
                message = response.get('message', {})
                tool_calls = message.get('tool_calls', [])
                logger.debug(f"Tool calls found: {len(tool_calls)}")
                return {
                    'content': message.get('content', ''),
                    'tool_calls': tool_calls
                }
            else:
                logger.error(f"Unexpected response format: {response}")
                return {'content': '', 'tool_calls': []}
            
        except Exception as e:
            logger.error(f"Chat error: {str(e)}")
            return {'content': f"[Error: {str(e)}]", 'tool_calls': []}
    
    def parse_action(self, response: str) -> Dict:
        """
        Parse LLM response for action commands.
        
        Legacy method kept for backwards compatibility with non-function-calling mode.
        Tries to extract JSON action from response.
        Returns structured action dict or defaults to 'respond' action.
        """
        import json
        
        # Try to find JSON in the response
        response = response.strip()
        
        # Look for JSON block
        json_start = response.find('{')
        json_end = response.rfind('}')
        
        if json_start != -1 and json_end != -1:
            try:
                json_str = response[json_start:json_end + 1]
                action = json.loads(json_str)
                
                # Validate action structure
                if 'action' in action:
                    return action
            except json.JSONDecodeError:
                pass
        
        # Default: treat as text response
        return {
            'action': 'respond',
            'text': response
        }
