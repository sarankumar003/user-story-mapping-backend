"""
Simplified configuration without environment variables
"""

class Settings:
    """Simple settings class"""
    
    # API Configuration
    API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = "your_openai_api_key_here"
    OPENAI_MODEL: str = "gpt-4"
    
    # Jira Configuration
    JIRA_BASE_URL: str = "your_jira_url_here"
    JIRA_USERNAME: str = "your_jira_username"
    JIRA_API_TOKEN: str = "your_jira_api_token"
    JIRA_PROJECT_KEY: str = "NT"
    
    # File Storage
    STORAGE_BASE_PATH: str = "./data/runs"
    UPLOAD_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: str = ".pdf,.docx,.doc"
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    
    # Run Manager
    MAX_RUN_HISTORY: int = 50

settings = Settings()

