#!/usr/bin/env python3
"""
Jira Configuration Helper
Provides easy configuration management for Jira operations.
"""

import os
from typing import Dict, Optional


class JiraConfig:
    """Jira configuration management"""
    
    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(__file__), 'jira_config.json')
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, str]:
        """Load configuration from file or environment variables"""
        config = {}
        
        # Try to load from config file first
        if os.path.exists(self.config_file):
            try:
                import json
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
        
        # Override with environment variables
        config.update({
            'base_url': os.getenv('JIRA_BASE_URL', config.get('base_url', '')),
            'username': os.getenv('JIRA_USERNAME', config.get('username', '')),
            'api_token': os.getenv('JIRA_API_TOKEN', config.get('api_token', '')),
        })
        
        return config
    
    def save_config(self, base_url: str, username: str, api_token: str):
        """Save configuration to file"""
        import json
        config = {
            'base_url': base_url,
            'username': username,
            'api_token': api_token
        }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"✅ Configuration saved to {self.config_file}")
        except Exception as e:
            print(f"❌ Error saving config: {e}")
    
    def get_credentials(self) -> tuple[str, str, str]:
        """Get Jira credentials"""
        base_url = self.config.get('base_url', '')
        username = self.config.get('username', '')
        api_token = self.config.get('api_token', '')
        
        if not all([base_url, username, api_token]):
            print("❌ Jira credentials not configured!")
            print("Please set the following environment variables or run the setup:")
            print("  JIRA_BASE_URL=https://your-domain.atlassian.net")
            print("  JIRA_USERNAME=your-email@domain.com")
            print("  JIRA_API_TOKEN=your-api-token")
            print("\nOr run: python jira_config.py setup")
            return "", "", ""
        
        return base_url, username, api_token
    
    def setup_interactive(self):
        """Interactive setup for Jira credentials"""
        print("🔧 Jira Configuration Setup")
        print("=" * 40)
        
        base_url = input("Jira Base URL (e.g., https://your-domain.atlassian.net): ").strip()
        username = input("Username/Email: ").strip()
        api_token = input("API Token: ").strip()
        
        if all([base_url, username, api_token]):
            self.save_config(base_url, username, api_token)
            print("✅ Configuration saved successfully!")
        else:
            print("❌ All fields are required!")


def main():
    """Command line interface for configuration"""
    import sys
    
    config = JiraConfig()
    
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        config.setup_interactive()
    else:
        base_url, username, api_token = config.get_credentials()
        if base_url and username and api_token:
            print("✅ Jira credentials are configured")
            print(f"Base URL: {base_url}")
            print(f"Username: {username}")
            print(f"API Token: {'*' * len(api_token)}")
        else:
            print("❌ Jira credentials not configured")
            print("Run: python jira_config.py setup")


if __name__ == "__main__":
    main()





