#!/usr/bin/env python3
"""
Setup script to help configure environment variables for StoryLab Backend
"""

import os
import sys

def setup_environment():
    """Interactive setup for environment variables"""
    
    print("🔧 StoryLab Backend Configuration Setup")
    print("=" * 50)
    
    # Get current environment variables
    current_env = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', ''),
        'JIRA_USERNAME': os.getenv('JIRA_USERNAME', ''),
        'JIRA_API_TOKEN': os.getenv('JIRA_API_TOKEN', ''),
    }
    
    print("\n📋 Current Configuration:")
    for key, value in current_env.items():
        if value:
            # Mask sensitive values
            masked_value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"  {key}: {masked_value}")
        else:
            print(f"  {key}: Not set")
    
    print("\n🔑 Required Environment Variables:")
    print("1. OPENAI_API_KEY - Your OpenAI API key")
    print("2. JIRA_USERNAME - Your Jira username/email")
    print("3. JIRA_API_TOKEN - Your Jira API token")
    
    print("\n💡 To set these variables:")
    print("Windows (Command Prompt):")
    print("  set OPENAI_API_KEY=your_key_here")
    print("  set JIRA_USERNAME=your_username_here")
    print("  set JIRA_API_TOKEN=your_token_here")
    
    print("\nWindows (PowerShell):")
    print("  $env:OPENAI_API_KEY='your_key_here'")
    print("  $env:JIRA_USERNAME='your_username_here'")
    print("  $env:JIRA_API_TOKEN='your_token_here'")
    
    print("\nLinux/Mac:")
    print("  export OPENAI_API_KEY=your_key_here")
    print("  export JIRA_USERNAME=your_username_here")
    print("  export JIRA_API_TOKEN=your_token_here")
    
    print("\n📝 Or create a .env file in the backend directory:")
    print("OPENAI_API_KEY=your_key_here")
    print("JIRA_USERNAME=your_username_here")
    print("JIRA_API_TOKEN=your_token_here")
    
    # Test configuration
    print("\n🧪 Testing Configuration...")
    try:
        from config import validate_config
        validate_config()
        print("✅ Configuration is valid!")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("\nPlease set the required environment variables and try again.")
        return False
    except Exception as e:
        print(f"⚠️  Warning: {e}")
    
    return True

if __name__ == "__main__":
    setup_environment()
