"""
LLM interface with streaming support.
Compatible with both Ollama and OpenAI-compatible APIs (like LM Studio).
"""

import json
import requests
import warnings
import logging
from typing import Iterator, Dict, List, Optional
from urllib.parse import urlparse

# Disable SSL warnings for self-signed certificates
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Setup logging (will be configured by main app)
logger = logging.getLogger(__name__)


class LLMClient:
    """Streaming LLM client supporting multiple backends."""
    
    def __init__(self, base_url: str, model_name: str, system_prompt: Optional[str] = None,
                 username: Optional[str] = None, password: Optional[str] = None,
                 context_length: Optional[int] = None):
        """
        Initialize LLM client.
        
        Args:
            base_url: API endpoint URL (e.g., http://localhost:1234/v1/chat/completions)
            model_name: Name of the model to use
            system_prompt: Optional system prompt
            username: Optional username for basic auth
            password: Optional password for basic auth
        """
        self.base_url = base_url
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.auth = (username, password) if username and password else None
        self.context_length = context_length
        
        # Detect API type based on URL
        self.api_type = self._detect_api_type(base_url)
    
    def _detect_api_type(self, url: str) -> str:
        """Detect if we're using Ollama or OpenAI-compatible API."""
        if 'ollama' in url or '/api/chat' in url or '/api/generate' in url:
            return 'ollama'
        return 'openai'
    
    def _build_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Build message list with optional system prompt."""
        if self.system_prompt and (not messages or messages[0]['role'] != 'system'):
            return [{'role': 'system', 'content': self.system_prompt}] + messages
        return messages
    
    def stream_chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, 
                    tools: Optional[List[Dict]] = None) -> Iterator[str]:
        """
        Stream chat completion responses.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            tools: Optional list of tool schemas for function calling
            
        Yields:
            Content chunks as they arrive
        """
        messages = self._build_messages(messages)
        
        if self.api_type == 'ollama':
            yield from self._stream_ollama(messages, temperature, tools)
        else:
            yield from self._stream_openai(messages, temperature, tools)
    
    def _stream_ollama(self, messages: List[Dict], temperature: float, tools: Optional[List[Dict]] = None) -> Iterator[str]:
        """Stream from Ollama API."""
        # Check if using /api/generate (prompt-based) or /api/chat (message-based)
        is_generate = '/api/generate' in self.base_url
        
        if is_generate:
            # For /api/generate, we need to use prompt instead of messages
            # Combine messages into a single prompt
            prompt_parts = []
            for msg in messages:
                role = msg.get('role', '')
                content = msg.get('content', '')
                if role == 'system':
                    prompt_parts.append(f"System: {content}")
                elif role == 'user':
                    prompt_parts.append(f"User: {content}")
                elif role == 'assistant':
                    prompt_parts.append(f"Assistant: {content}")
            
            prompt = '\n\n'.join(prompt_parts) + '\n\nAssistant:'
            
            payload = {
                'model': self.model_name,
                'prompt': prompt,
                'stream': True,
                'options': {
                    'temperature': temperature
                }
            }
        else:
            # For /api/chat, use messages format
            payload = {
                'model': self.model_name,
                'messages': messages,
                'stream': True,
                'options': {
                    'temperature': temperature
                }
            }
            
            # Add tools if provided (only for /api/chat)
            if tools:
                payload['tools'] = tools
        
        # Inject context length for Ollama, if provided
        try:
            if self.context_length and isinstance(payload, dict):
                options = payload.setdefault('options', {})
                # Ollama expects 'num_ctx' (context window tokens)
                options['num_ctx'] = int(self.context_length)
        except Exception:
            pass

        logger.debug(f"Ollama request to {self.base_url}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        logger.debug(f"Auth: {'Enabled' if self.auth else 'Disabled'}")
        
        try:
            with requests.post(self.base_url, json=payload, stream=True, timeout=120, auth=self.auth, verify=False) as response:
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                response.raise_for_status()
                
                line_count = 0
                for line in response.iter_lines():
                    if line:
                        line_count += 1
                        logger.debug(f"Line {line_count}: {line[:200]}")  # Log first 200 chars
                        try:
                            chunk = json.loads(line)
                            # Handle both /api/chat and /api/generate formats
                            if 'message' in chunk and 'content' in chunk['message']:
                                content = chunk['message']['content']
                                if content:
                                    yield content
                            elif 'response' in chunk:  # /api/generate format
                                content = chunk['response']
                                if content:
                                    yield content
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e}, Line: {line}")
                            continue
                
                logger.debug(f"Total lines received: {line_count}")
                            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            yield f"\n[Error: {str(e)}]"
    
    def _stream_openai(self, messages: List[Dict], temperature: float, tools: Optional[List[Dict]] = None) -> Iterator[str]:
        """Stream from OpenAI-compatible API (LM Studio, etc.)."""
        payload = {
            'model': self.model_name,
            'messages': messages,
            'stream': True,
            'temperature': temperature
        }
        
        # Add tools if provided
        if tools:
            payload['tools'] = tools
        
        # Best-effort: map context length to OpenAI-compatible 'max_tokens' (output limit)
        try:
            if self.context_length:
                payload['max_tokens'] = int(self.context_length)
        except Exception:
            pass

        try:
            with requests.post(self.base_url, json=payload, stream=True, timeout=120, auth=self.auth, verify=False) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        
                        # OpenAI streaming format: "data: {json}"
                        if line.startswith('data: '):
                            line = line[6:]  # Remove "data: " prefix
                            
                            if line.strip() == '[DONE]':
                                break
                            
                            try:
                                chunk = json.loads(line)
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
                                
        except requests.exceptions.RequestException as e:
            yield f"\n[Error: {str(e)}]"
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, 
             tools: Optional[List[Dict]] = None) -> Dict:
        """
        Non-streaming chat completion (collects full response including tool calls).
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            tools: Optional list of tool schemas
            
        Returns:
            Dict with 'content' (text) and optional 'tool_calls' (list)
        """
        messages = self._build_messages(messages)
        
        payload = {
            'model': self.model_name,
            'messages': messages,
            'temperature': temperature,
            'stream': False
        }
        
        if tools:
            payload['tools'] = tools
        
        # Inject context length per backend
        try:
            if self.api_type == 'ollama':
                options = payload.setdefault('options', {})
                options['temperature'] = temperature
                if self.context_length:
                    options['num_ctx'] = int(self.context_length)
            else:
                if self.context_length:
                    payload['max_tokens'] = int(self.context_length)
        except Exception:
            pass
        
        try:
            logger.debug(f"Non-streaming request to {self.base_url}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            response = requests.post(self.base_url, json=payload, timeout=120, auth=self.auth, verify=False)
            logger.debug(f"Response status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Response data: {json.dumps(data, indent=2)[:500]}")
            
            # Parse response based on API type
            if self.api_type == 'ollama':
                message = data.get('message', {})
                return {
                    'content': message.get('content', ''),
                    'tool_calls': message.get('tool_calls', [])
                }
            else:  # OpenAI format
                if 'choices' in data and len(data['choices']) > 0:
                    message = data['choices'][0].get('message', {})
                    return {
                        'content': message.get('content', ''),
                        'tool_calls': message.get('tool_calls', [])
                    }
            
            return {'content': '', 'tool_calls': []}
            
        except requests.exceptions.RequestException as e:
            return {'content': f"[Error: {str(e)}]", 'tool_calls': []}
    
    def parse_action(self, response: str) -> Dict:
        """
        Parse LLM response for action commands.
        
        Tries to extract JSON action from response.
        Returns structured action dict or defaults to 'respond' action.
        """
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

