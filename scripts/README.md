# Jira Operations Scripts

This directory contains comprehensive Python scripts for interacting with Jira through the MCP Atlassian server.

## Files

- `jira_operations.py` - Main script with all Jira operations
- `jira_config.py` - Configuration management helper
- `README.md` - This documentation

## Setup

### 1. Configure Jira Credentials

You have two options:

#### Option A: Interactive Setup
```bash
cd scripts
python jira_config.py setup
```

#### Option B: Environment Variables
```bash
export JIRA_BASE_URL="https://your-domain.atlassian.net"
export JIRA_USERNAME="your-email@domain.com"
export JIRA_API_TOKEN="your-api-token"
```

### 2. Install Dependencies

Make sure you have the MCP Atlassian server dependencies installed:
```bash
cd mcp-atlassian
pip install -e .
```

## Usage

### Command Line Interface

```bash
# List all projects
python jira_operations.py projects

# Get specific project
python jira_operations.py project WEB

# List users in a project
python jira_operations.py users WEB

# Search users
python jira_operations.py search-users john

# Get issue types for a project
python jira_operations.py issue-types WEB

# List priorities
python jira_operations.py priorities

# List statuses
python jira_operations.py statuses

# Get specific issue
python jira_operations.py issue WEB-123

# Search issues with JQL
python jira_operations.py search "project = WEB AND status = 'To Do'"

# Get available transitions for an issue
python jira_operations.py transitions WEB-123

# Get comments for an issue
python jira_operations.py comments WEB-123

# Get attachments for an issue
python jira_operations.py attachments WEB-123

# Run example usage
python jira_operations.py example
```

### Programmatic Usage

```python
import asyncio
from jira_operations import JiraOperations

async def main():
    # Initialize with credentials
    jira = JiraOperations(
        base_url="https://your-domain.atlassian.net",
        username="your-email@domain.com",
        api_token="your-api-token"
    )
    
    # Connect
    await jira.connect()
    
    try:
        # Get all projects
        projects = await jira.get_projects()
        
        # Get users from a project
        users = await jira.get_users("WEB")
        
        # Search for issues
        issues = await jira.search_issues("project = WEB AND status = 'To Do'")
        
        # Create a new issue
        new_issue_data = {
            "project": {"key": "WEB"},
            "summary": "Test issue from script",
            "description": "This is a test issue",
            "issue_type": {"name": "Task"},
            "priority": {"name": "Medium"}
        }
        new_issue = await jira.create_issue(new_issue_data)
        
        # Update an issue
        update_data = {
            "summary": "Updated summary",
            "description": "Updated description"
        }
        await jira.update_issue("WEB-123", update_data)
        
        # Add a comment
        await jira.add_comment("WEB-123", "This is a comment from the script")
        
        # Transition an issue
        transitions = await jira.get_issue_transitions("WEB-123")
        if transitions:
            await jira.transition_issue("WEB-123", transitions[0].id, "Moving to next status")
        
    finally:
        await jira.disconnect()

# Run the example
asyncio.run(main())
```

## Available Operations

### Project Operations
- `get_projects()` - Get all projects
- `get_project(project_key)` - Get specific project
- `get_project_components(project_key)` - Get project components
- `get_project_versions(project_key)` - Get project versions

### User Operations
- `get_users(project_key=None)` - Get users (optionally filtered by project)
- `get_user(username)` - Get specific user
- `search_users(query)` - Search users by query

### Issue Type Operations
- `get_issue_types(project_key=None)` - Get issue types (optionally filtered by project)

### Priority & Status Operations
- `get_priorities()` - Get all priorities
- `get_statuses()` - Get all statuses

### Issue Operations
- `create_issue(issue_data)` - Create a new issue
- `get_issue(issue_key)` - Get specific issue
- `update_issue(issue_key, update_data)` - Update an issue
- `delete_issue(issue_key)` - Delete an issue
- `search_issues(jql, max_results=50)` - Search issues using JQL

### Transition Operations
- `get_issue_transitions(issue_key)` - Get available transitions
- `transition_issue(issue_key, transition_id, comment=None)` - Transition an issue

### Comment Operations
- `get_issue_comments(issue_key)` - Get comments for an issue
- `add_comment(issue_key, comment_body)` - Add a comment
- `update_comment(issue_key, comment_id, comment_body)` - Update a comment
- `delete_comment(issue_key, comment_id)` - Delete a comment

### Attachment Operations
- `get_issue_attachments(issue_key)` - Get attachments for an issue
- `add_attachment(issue_key, file_path, filename=None)` - Add an attachment
- `delete_attachment(attachment_id)` - Delete an attachment

## Error Handling

All operations include comprehensive error handling and will print helpful error messages. The methods return `None` or empty lists on failure, so you can check the return values in your code.

## Examples

### Create an Epic with Stories and Subtasks

```python
async def create_epic_with_stories():
    jira = JiraOperations(base_url, username, api_token)
    await jira.connect()
    
    try:
        # Create Epic
        epic_data = {
            "project": {"key": "WEB"},
            "summary": "User Authentication System",
            "description": "Complete user authentication system with SSO",
            "issue_type": {"name": "Epic"},
            "priority": {"name": "High"}
        }
        epic = await jira.create_issue(epic_data)
        
        if epic:
            # Create Story
            story_data = {
                "project": {"key": "WEB"},
                "summary": "Implement Login API",
                "description": "Create REST API for user login",
                "issue_type": {"name": "Story"},
                "priority": {"name": "Medium"},
                "parent": {"key": epic.key}
            }
            story = await jira.create_issue(story_data)
            
            if story:
                # Create Subtask
                subtask_data = {
                    "project": {"key": "WEB"},
                    "summary": "Design API endpoints",
                    "description": "Design REST endpoints for login",
                    "issue_type": {"name": "Sub-task"},
                    "priority": {"name": "Low"},
                    "parent": {"key": story.key}
                }
                subtask = await jira.create_issue(subtask_data)
    
    finally:
        await jira.disconnect()
```

### Bulk Issue Creation

```python
async def create_bulk_issues():
    jira = JiraOperations(base_url, username, api_token)
    await jira.connect()
    
    try:
        issues_data = [
            {
                "project": {"key": "WEB"},
                "summary": f"Task {i}",
                "description": f"Description for task {i}",
                "issue_type": {"name": "Task"},
                "priority": {"name": "Medium"}
            }
            for i in range(1, 6)
        ]
        
        created_issues = []
        for issue_data in issues_data:
            issue = await jira.create_issue(issue_data)
            if issue:
                created_issues.append(issue)
        
        print(f"Created {len(created_issues)} issues")
    
    finally:
        await jira.disconnect()
```

## Troubleshooting

### Common Issues

1. **Connection Failed**: Check your Jira URL, username, and API token
2. **Permission Denied**: Ensure your user has the necessary permissions in Jira
3. **Project Not Found**: Verify the project key exists and you have access
4. **Invalid JQL**: Check your JQL syntax for search queries

### Debug Mode

To see more detailed error information, you can modify the script to include more verbose logging or catch specific exceptions.

## Security Notes

- Never commit your API token to version control
- Use environment variables or the config file for credentials
- The config file is created locally and should be added to `.gitignore`
- API tokens should be rotated regularly for security





