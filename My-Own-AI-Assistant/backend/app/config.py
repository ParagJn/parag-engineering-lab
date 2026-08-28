"""
Application configuration.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""
    
    # Paths
    BASE_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = BASE_DIR / "data"
    SESSIONS_DIR = DATA_DIR / "sessions"
    DOCUMENTS_DIR = DATA_DIR / "documents"
    
    # IBM ICA Model Configuration
    IBM_ICA_API_KEY = os.getenv("IBM_ICA_API_KEY", "")
    IBM_ICA_ENDPOINT = os.getenv("IBM_ICA_ENDPOINT", "")
    IBM_ICA_MODEL_ID = os.getenv("IBM_ICA_MODEL_ID", "claude-sonnet-5")
    IBM_ICA_INSECURE_TLS = os.getenv("IBM_ICA_INSECURE_TLS", "false").lower() in ("true", "1", "yes")
    
    # Model settings
    MODEL_TIMEOUT = int(os.getenv("MODEL_TIMEOUT", "60"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "100000"))
    
    # API settings
    API_PREFIX = "/api"
    CORS_ORIGINS = [
        "http://localhost:5173",  # Vite default
        "http://localhost:3000",
    ]
    
    # File upload settings
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {
        ".pdf", ".docx", ".doc", ".txt", ".md", ".markdown"
    }
    
    @classmethod
    def validate(cls):
        """Validate required configuration."""
        errors = []
        
        if not cls.IBM_ICA_API_KEY:
            errors.append("IBM_ICA_API_KEY is required")
        if not cls.IBM_ICA_ENDPOINT:
            errors.append("IBM_ICA_ENDPOINT is required")
            
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist."""
        cls.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        cls.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
