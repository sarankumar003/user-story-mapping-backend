"""
Configuration settings for StoryLab Backend
"""
import os
from pathlib import Path

# API Configuration
#API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
#FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
#ENVIRONMENT =  "development"

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4"

# Jira Configuration
JIRA_BASE_URL = "https://crayonhackathon2025.atlassian.net"
JIRA_USERNAME = "saranbharathi22333@gmail.com"
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = "CRAYOT"

# File Storage
STORAGE_BASE_PATH = "./data/runs"
UPLOAD_MAX_SIZE = "10485760"  
ALLOWED_FILE_TYPES = ".pdf,.docx,.doc"

# CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# Run Manager
MAX_RUN_HISTORY = "50"

# Paths
BACKEND_ROOT = Path(__file__).parent
DATA_DIR = BACKEND_ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"
UPLOADS_DIR = BACKEND_ROOT / "uploads"
LOGS_DIR = BACKEND_ROOT / "logs"

# Ensure directories exist
for directory in [DATA_DIR, RUNS_DIR, UPLOADS_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# Validation
def validate_config():
    """Validate required configuration"""
    errors = []
    
    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is required")
    
    if not JIRA_USERNAME:
        errors.append("JIRA_USERNAME is required")
    
    if not JIRA_API_TOKEN:
        errors.append("JIRA_API_TOKEN is required")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    return True

# Validate on import
if __name__ != "__main__":
    try:
        validate_config()
    except ValueError as e:
        print(f"Warning: {e}")
        print("Please set the required environment variables:")
        print("- OPENAI_API_KEY")
        print("- JIRA_USERNAME") 
        print("- JIRA_API_TOKEN")
