"""
Application configuration settings
"""

import sys
from pathlib import Path

# Add backend root to path to import config
backend_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_root))

try:
    from config import (
        API_BASE_URL,
        FRONTEND_URL,
        ENVIRONMENT,
        OPENAI_API_KEY,
        OPENAI_MODEL,
        JIRA_BASE_URL,
        JIRA_USERNAME,
        JIRA_API_TOKEN,
        JIRA_PROJECT_KEY,
        STORAGE_BASE_PATH,
        UPLOAD_MAX_SIZE,
        ALLOWED_FILE_TYPES,
        ALLOWED_ORIGINS,
        MAX_RUN_HISTORY
    )
except ImportError:
    # Fallback values if config.py is not available
    API_BASE_URL = "http://localhost:8001"
    FRONTEND_URL = "http://localhost:3000"
    ENVIRONMENT = "development"
    OPENAI_API_KEY = ""
    OPENAI_MODEL = "gpt-4"
    JIRA_BASE_URL = "https://crayonhackathon2025.atlassian.net"
    JIRA_USERNAME = ""
    JIRA_API_TOKEN = ""
    JIRA_PROJECT_KEY = "CRAYOT"
    STORAGE_BASE_PATH = "./data/runs"
    UPLOAD_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES = [".pdf", ".docx", ".doc"]
    ALLOWED_ORIGINS = ["http://localhost:3000"]
    MAX_RUN_HISTORY = 50


class Settings:
    """Application settings"""
    
    # API Configuration
    API_BASE_URL: str = API_BASE_URL
    FRONTEND_URL: str = FRONTEND_URL
    ENVIRONMENT: str = ENVIRONMENT
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = OPENAI_API_KEY
    OPENAI_MODEL: str = OPENAI_MODEL
    
    # Jira Configuration
    JIRA_BASE_URL: str = JIRA_BASE_URL
    JIRA_USERNAME: str = JIRA_USERNAME
    JIRA_API_TOKEN: str = JIRA_API_TOKEN
    JIRA_PROJECT_KEY: str = JIRA_PROJECT_KEY
    
    # File Storage
    STORAGE_BASE_PATH: str = STORAGE_BASE_PATH
    UPLOAD_MAX_SIZE: int = UPLOAD_MAX_SIZE
    ALLOWED_FILE_TYPES: list = ALLOWED_FILE_TYPES
    
    # CORS
    ALLOWED_ORIGINS: list = ALLOWED_ORIGINS
    
    # Run Manager
    MAX_RUN_HISTORY: int = MAX_RUN_HISTORY


settings = Settings()
