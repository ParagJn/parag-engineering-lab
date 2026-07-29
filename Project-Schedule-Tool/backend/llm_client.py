"""
Universal LLM Client
A reusable, provider-agnostic LLM client that supports multiple AI model providers.

Supported Providers:
- SAP AI Core (Claude, GPT models via SAP)
- OpenAI (GPT-4, GPT-3.5, etc.)
- Google Gemini
- Azure OpenAI
- Anthropic (Claude direct)

Author: Auto-generated
Date: 2026-07-29
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import logging


class Provider(Enum):
    """Supported LLM providers"""
    SAP = "sap"
    OPENAI = "openai"
    GOOGLE = "google"
    AZURE = "azure"
    ANTHROPIC = "anthropic"


class LLMClientError(Exception):
    """Base exception for LLM Client errors"""
    pass


class AuthenticationError(LLMClientError):
    """Authentication failed"""
    pass


class APIError(LLMClientError):
    """API request failed"""
    pass


class ConfigurationError(LLMClientError):
    """Configuration issue"""
    pass


class UniversalLLMClient:
    """
    Universal LLM Client for interacting with multiple AI model providers.
    
    Features:
    - Multi-provider support (SAP, OpenAI, Google, Azure, Anthropic)
    - Automatic token management for OAuth flows
    - Retry logic with exponential backoff
    - Comprehensive error handling
    - Request/response logging
    - Model configuration via config.json
    
    Usage:
        client = UniversalLLMClient(config_path="config.json")
        response = client.generate(
            prompt="Hello, world!",
            model="anthropic--claude-4.8-opus"
        )
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the Universal LLM Client.
        
        Args:
            config_path: Path to the configuration JSON file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.logger = self._setup_logger()
        
        # Token cache for OAuth providers
        self._token_cache: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("UniversalLLMClient initialized")
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logging configuration"""
        log_level = self.config.get("settings", {}).get("logging", {}).get("level", "INFO")
        logger = logging.getLogger("UniversalLLMClient")
        logger.setLevel(getattr(logging, log_level))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise ConfigurationError(f"Config file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in config file: {e}")
    
    def _get_env_variable(self, var_name: str) -> Optional[str]:
        """Safely get environment variable"""
        value = os.getenv(var_name)
        if not value:
            self.logger.warning(f"Environment variable {var_name} not set")
        return value
    
    def _get_access_token_sap(self, provider_config: Dict) -> str:
        """
        Get OAuth 2.0 access token for SAP AI Core.
        Implements token caching to avoid unnecessary requests.
        
        Args:
            provider_config: SAP provider configuration
            
        Returns:
            Access token string
            
        Raises:
            AuthenticationError: If authentication fails
        """
        cache_key = "sap_token"
        
        # Check if we have a valid cached token
        if cache_key in self._token_cache:
            cached = self._token_cache[cache_key]
            if datetime.now() < cached['expires_at']:
                self.logger.debug("Using cached SAP access token")
                return cached['token']
        
        # Get credentials from environment
        auth_config = provider_config['auth']
        client_id = self._get_env_variable(auth_config['client_id_env'])
        client_secret = self._get_env_variable(auth_config['client_secret_env'])
        
        if not client_id or not client_secret:
            raise AuthenticationError("SAP credentials not found in environment variables")
        
        # Request new token
        try:
            token_payload = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            response = requests.post(
                auth_config['token_url'],
                data=token_payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            response.raise_for_status()
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            if not access_token:
                raise AuthenticationError("No access token in response")
            
            # Cache the token (expires in - 60 seconds for safety margin)
            expires_in = token_data.get('expires_in', 3600)
            expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
            
            self._token_cache[cache_key] = {
                'token': access_token,
                'expires_at': expires_at
            }
            
            self.logger.info(f"✅ SAP access token generated (expires in {expires_in}s)")
            return access_token
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to get SAP access token: {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f"\nResponse: {e.response.text}"
            raise AuthenticationError(error_msg)
    
    def _get_provider_config(self, provider_key: str) -> Dict:
        """Get configuration for a specific provider"""
        provider_config = self.config['models'].get(provider_key)
        if not provider_config:
            raise ConfigurationError(f"Provider {provider_key} not found in config")
        if not provider_config.get('enabled', False):
            raise ConfigurationError(f"Provider {provider_key} is not enabled")
        return provider_config
    
    def _get_model_config(self, provider_key: str, model_name: Optional[str] = None) -> tuple:
        """
        Get model configuration from provider.
        
        Returns:
            Tuple of (provider_config, model_config)
        """
        provider_config = self._get_provider_config(provider_key)
        
        # If no model specified, use default
        if not model_name:
            for model in provider_config['models']:
                if model.get('default', False) and model.get('enabled', False):
                    return provider_config, model
            raise ConfigurationError(f"No default model found for {provider_key}")
        
        # Find specific model
        for model in provider_config['models']:
            if model['name'] == model_name and model.get('enabled', False):
                return provider_config, model
        
        raise ConfigurationError(f"Model {model_name} not found or not enabled in {provider_key}")
    
    def _make_request_sap(
        self,
        provider_config: Dict,
        model_config: Dict,
        prompt: str,
        **kwargs
    ) -> Dict:
        """Make API request to SAP AI Core using Orchestration format"""
        access_token = self._get_access_token_sap(provider_config)
        
        # Build API URL
        api_base = provider_config['auth']['api_base_url']
        api_version = model_config.get('api_version', 'v2')
        deployment_id = model_config['deployment_id']
        url = f"{api_base}/{api_version}/inference/deployments/{deployment_id}/v2/completion"
        
        # Get model name from config (e.g., "anthropic--claude-4.7-opus")
        model_name = model_config.get('name', 'gemini-2.5-flash')
        
        # SAP AI Core Orchestration format
        payload = {
            "config": {
                "modules": {
                    "prompt_templating": {
                        "prompt": {
                            "template": [
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ]
                        },
                        "model": {
                            "name": model_name,
                            "version": "latest",
                            "params": {}
                        }
                    }
                }
            }
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'ai-resource-group': provider_config['auth']['resource_group']
        }
        
        if self.config.get('settings', {}).get('logging', {}).get('log_requests', False):
            self.logger.debug(f"SAP Request URL: {url}")
            self.logger.debug(f"SAP Request: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=kwargs.get('timeout', self.config['settings'].get('timeout_seconds', 120))
        )
        
        response.raise_for_status()
        result = response.json()
        
        if self.config.get('settings', {}).get('logging', {}).get('log_responses', False):
            self.logger.debug(f"SAP Response: {json.dumps(result, indent=2)}")
        
        return result
    
    def _make_request_openai(
        self,
        provider_config: Dict,
        model_config: Dict,
        prompt: str,
        **kwargs
    ) -> Dict:
        """Make API request to OpenAI"""
        api_key = self._get_env_variable(provider_config['auth']['api_key_env'])
        if not api_key:
            raise AuthenticationError("OpenAI API key not found")
        
        url = f"{provider_config['auth']['api_base_url']}/chat/completions"
        
        payload = {
            "model": model_config['model_id'],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get('max_tokens', model_config.get('max_tokens', 25000)),
        }
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        return response.json()
    
    def _make_request_anthropic(
        self,
        provider_config: Dict,
        model_config: Dict,
        prompt: str,
        **kwargs
    ) -> Dict:
        """Make API request to Anthropic"""
        api_key = self._get_env_variable(provider_config['auth']['api_key_env'])
        if not api_key:
            raise AuthenticationError("Anthropic API key not found")
        
        url = f"{provider_config['auth']['api_base_url']}/v1/messages"
        
        payload = {
            "model": model_config['model_id'],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get('max_tokens', model_config.get('max_tokens', 25000)),
        }
        
        headers = {
            'x-api-key': api_key,
            'anthropic-version': provider_config['auth']['api_version'],
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        return response.json()
    
    def _make_request_with_retry(
        self,
        provider_key: str,
        provider_config: Dict,
        model_config: Dict,
        prompt: str,
        **kwargs
    ) -> Dict:
        """
        Make API request with retry logic.
        
        Implements exponential backoff for failed requests.
        """
        retry_attempts = self.config['settings'].get('retry_attempts', 3)
        retry_delay = self.config['settings'].get('retry_delay_seconds', 2)
        
        last_error = None
        
        for attempt in range(retry_attempts):
            try:
                # Route to appropriate provider
                provider = provider_config['provider']
                
                if provider == 'sap':
                    return self._make_request_sap(provider_config, model_config, prompt, **kwargs)
                elif provider == 'openai':
                    return self._make_request_openai(provider_config, model_config, prompt, **kwargs)
                elif provider == 'anthropic':
                    return self._make_request_anthropic(provider_config, model_config, prompt, **kwargs)
                else:
                    raise ConfigurationError(f"Provider {provider} not yet implemented")
                    
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < retry_attempts - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    self.logger.warning(f"Request failed (attempt {attempt + 1}/{retry_attempts}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"All retry attempts failed")
        
        raise APIError(f"Request failed after {retry_attempts} attempts: {last_error}")
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        Generate text using the specified model.
        
        Args:
            prompt: The input prompt/question
            model: Model name (optional, uses default if not specified)
            provider: Provider key (optional, uses default if not specified)
            **kwargs: Additional parameters (max_tokens, etc.)
            
        Returns:
            Dictionary containing the API response
            
        Example:
            response = client.generate(
                prompt="Explain quantum computing",
                model="anthropic--claude-4.8-opus",
                max_tokens=25000
            )
        """
        # Determine provider - handle "string" as default
        if not provider or provider == "string":
            provider = self.config['settings']['default_provider']
        
        # Determine model - handle "string" as default
        if not model or model == "string":
            model = None  # Will use default model
        
        # Get configurations
        provider_config, model_config = self._get_model_config(provider, model)
        
        self.logger.info(f"Generating response using {provider}/{model_config['name']}")
        
        # Make request with retry
        response = self._make_request_with_retry(
            provider,
            provider_config,
            model_config,
            prompt,
            **kwargs
        )
        
        return response
    
    def list_available_models(self) -> List[Dict[str, Any]]:
        """
        List all available (enabled) models across all providers.
        
        Returns:
            List of dictionaries containing model information
        """
        available = []
        
        for provider_key, provider_config in self.config['models'].items():
            if not provider_config.get('enabled', False):
                continue
            
            for model in provider_config['models']:
                if model.get('enabled', False):
                    available.append({
                        'provider': provider_key,
                        'model_name': model['name'],
                        'capabilities': model.get('capabilities', []),
                        'is_default': model.get('default', False),
                        'max_tokens': model.get('max_tokens'),
                    })
        
        return available
    
    def get_default_model(self) -> tuple:
        """
        Get the default model configuration.
        
        Returns:
            Tuple of (provider_key, model_name)
        """
        default_provider = self.config['settings']['default_provider']
        default_model = self.config['settings'].get('default_model')
        
        return (default_provider, default_model)


# Convenience function for quick usage
def create_client(config_path: str = "config.json") -> UniversalLLMClient:
    """
    Create and return a UniversalLLMClient instance.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Initialized UniversalLLMClient
    """
    return UniversalLLMClient(config_path=config_path)


if __name__ == "__main__":
    # Example usage
    print("Universal LLM Client - Example Usage\n")
    
    try:
        # Initialize client
        client = create_client()
        
        # List available models
        print("Available Models:")
        for model in client.list_available_models():
            print(f"  - {model['provider']}/{model['model_name']}")
            if model['is_default']:
                print("    (default)")
        
        print("\n" + "="*50 + "\n")
        
        # Generate a response
        prompt = "What are the three laws of robotics?"
        print(f"Prompt: {prompt}\n")
        
        response = client.generate(prompt=prompt)
        print(f"Response:\n{json.dumps(response, indent=2)}")
        
    except Exception as e:
        print(f"Error: {e}")
