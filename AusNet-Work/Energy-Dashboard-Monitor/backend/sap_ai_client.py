"""
SAP AI Core Client
Handles authentication and API calls to SAP AI Core for Gemini 2.5 Pro model.
"""

import os
import re
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class SAPAIClient:
    """Client for interacting with SAP AI Core Orchestration API."""
    
    def __init__(self):
        """Initialize SAP AI Core client with credentials from environment."""
        self.client_id = os.getenv('SAP_CLIENT_ID')
        self.client_secret = os.getenv('SAP_CLIENT_SECRET')
        self.token_url = os.getenv('SAP_TOKEN_URL')
        self.api_url = os.getenv('SAP_API_URL')
        self.resource_group = os.getenv('SAP_RESOURCE_GROUP')
        
        # Validate required credentials
        if not all([self.client_id, self.client_secret, self.token_url, self.api_url, self.resource_group]):
            raise ValueError("Missing required SAP AI Core credentials in environment variables")
        
        self._access_token: Optional[str] = None
        self._token_expires_in: Optional[int] = None
    
    def get_access_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        Generate OAuth 2.0 access token using SAP AI Core service key credentials.
        
        Args:
            force_refresh: Force token refresh even if cached token exists
            
        Returns:
            Access token string or None if authentication fails
        """
        # Return cached token if available and not forcing refresh
        if self._access_token and not force_refresh:
            return self._access_token
        
        try:
            token_payload = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(
                self.token_url,
                data=token_payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            response.raise_for_status()
            token_data = response.json()
            
            self._access_token = token_data.get('access_token')
            self._token_expires_in = token_data.get('expires_in')
            
            print(f"✅ Access token generated successfully")
            print(f"Token expires in: {self._token_expires_in} seconds")
            
            return self._access_token
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Error generating access token: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None
    
    def generate_image_content(
        self, 
        prompt: str, 
        model_name: str = "gemini-2.5-pro",
        temperature: float = 0.7,
        timeout: int = 90
    ) -> Optional[Dict[str, Any]]:
        """
        Request image/visual content from Gemini 2.5 Pro via SAP AI Core Orchestration API.
        
        Args:
            prompt: The prompt describing the image to generate
            model_name: Model name (default: gemini-2.5-pro)
            temperature: Model temperature parameter (default: 0.7)
            timeout: Request timeout in seconds (default: 90)
            
        Returns:
            Response JSON or None if request fails
        """
        access_token = self.get_access_token()
        if not access_token:
            print("❌ Cannot proceed without access token")
            return None
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "AI-Resource-Group": self.resource_group,
            }

            payload = {
                "config": {
                    "modules": {
                        "prompt_templating": {
                            "prompt": {
                                "template": [
                                    {
                                        "role": "system",
                                        "content": (
                                            "You are a creative SVG designer. "
                                            "When asked to create a glyph or image, respond with "
                                            "ONLY a complete, self-contained SVG element — "
                                            "no markdown fences, no explanation, just the raw SVG."
                                        ),
                                    },
                                    {"role": "user", "content": prompt},
                                ]
                            },
                            "model": {
                                "name": model_name,
                                "version": "latest",
                                "params": {"temperature": temperature},
                            },
                        }
                    }
                }
            }

            print(f"🎨 Sending image-generation request to {model_name}...")
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=payload, 
                timeout=timeout
            )
            response.raise_for_status()
            
            print(f"✅ Request successful")
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"   Body: {e.response.text[:500]}")
            return None
    
    def extract_svg_from_response(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract SVG content from API response.
        
        Args:
            response: API response JSON
            
        Returns:
            SVG string or None if not found
        """
        if not response or "final_result" not in response:
            return None
        
        choices = response["final_result"].get("choices", [])
        if not choices:
            return None
        
        raw_content = choices[0]["message"]["content"]
        
        # Extract the SVG block from the model response
        svg_match = re.search(r"(<svg[\s\S]*?</svg>)", raw_content, re.IGNORECASE)
        
        if svg_match:
            return svg_match.group(1)
        
        # If no SVG found, return raw content for debugging
        print("⚠️  No SVG block found in response")
        return raw_content
    
    def get_token_usage(self, response: Dict[str, Any]) -> Dict[str, int]:
        """
        Extract token usage information from API response.
        
        Args:
            response: API response JSON
            
        Returns:
            Dictionary with token usage stats
        """
        if not response or "final_result" not in response:
            return {}
        
        usage = response["final_result"].get("usage", {})
        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0)
        }

# Made with Bob
