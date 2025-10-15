#!/usr/bin/env python3
"""
Comprehensive Jira Operations Script
Provides all available Jira operations from the MCP Atlassian server.
Use this script to perform any Jira operation programmatically.
"""

import asyncio
import json
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
import os

# Add the mcp-atlassian directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp-atlassian', 'src'))

from mcp_atlassian.jira.servers import JiraServer
from mcp_atlassian.jira.models import (
    Issue, IssueType, Project, User, Component, Version, 
    Priority, Status, Transition, Comment, Attachment,
    CreateIssueRequest, UpdateIssueRequest, SearchIssuesRequest
)


class JiraOperations:
    """Comprehensive Jira operations wrapper"""
    
    def __init__(self, base_url: str, username: str, api_token: str):
        """Initialize Jira connection"""
        self.server = JiraServer(base_url, username, api_token)
        self.base_url = base_url
        self.username = username
        
    async def connect(self):
        """Establish connection to Jira"""
        try:
            await self.server.connect()
            print(f"✅ Connected to Jira at {self.base_url}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to Jira: {e}")
            return False
    
    async def disconnect(self):
        """Close Jira connection"""
        try:
            await self.server.disconnect()
            print("✅ Disconnected from Jira")
        except Exception as e:
            print(f"❌ Error disconnecting: {e}")

    # ==================== PROJECT OPERATIONS ====================
    
    async def get_projects(self) -> List[Project]:
        """Get all projects"""
        try:
            projects = await self.server.list_projects()
            print(f"📋 Found {len(projects)} projects")
            return projects
        except Exception as e:
            print(f"❌ Error getting projects: {e}")
            return []
    
    async def get_project(self, project_key: str) -> Optional[Project]:
        """Get specific project by key"""
        try:
            project = await self.server.get_project(project_key)
            print(f"📋 Project {project_key}: {project.name}")
            return project
        except Exception as e:
            print(f"❌ Error getting project {project_key}: {e}")
            return None
    
    async def get_project_components(self, project_key: str) -> List[Component]:
        """Get components for a project"""
        try:
            components = await self.server.get_project_components(project_key)
            print(f"🧩 Found {len(components)} components in {project_key}")
            return components
        except Exception as e:
            print(f"❌ Error getting components for {project_key}: {e}")
            return []
    
    async def get_project_versions(self, project_key: str) -> List[Version]:
        """Get versions for a project"""
        try:
            versions = await self.server.get_project_versions(project_key)
            print(f"🏷️ Found {len(versions)} versions in {project_key}")
            return versions
        except Exception as e:
            print(f"❌ Error getting versions for {project_key}: {e}")
            return []

    # ==================== USER OPERATIONS ====================
    
    async def get_users(self, project_key: Optional[str] = None) -> List[User]:
        """Get users (optionally filtered by project)"""
        try:
            if project_key:
                users = await self.server.get_project_users(project_key)
                print(f"👥 Found {len(users)} users in project {project_key}")
            else:
                users = await self.server.get_users()
                print(f"👥 Found {len(users)} users")
            return users
        except Exception as e:
            print(f"❌ Error getting users: {e}")
            return []
    
    async def get_user(self, username: str) -> Optional[User]:
        """Get specific user by username"""
        try:
            user = await self.server.get_user(username)
            print(f"👤 User {username}: {user.display_name}")
            return user
        except Exception as e:
            print(f"❌ Error getting user {username}: {e}")
            return None
    
    async def search_users(self, query: str) -> List[User]:
        """Search users by query"""
        try:
            users = await self.server.search_users(query)
            print(f"🔍 Found {len(users)} users matching '{query}'")
            return users
        except Exception as e:
            print(f"❌ Error searching users: {e}")
            return []

    # ==================== ISSUE TYPE OPERATIONS ====================
    
    async def get_issue_types(self, project_key: Optional[str] = None) -> List[IssueType]:
        """Get issue types (optionally filtered by project)"""
        try:
            if project_key:
                issue_types = await self.server.get_project_issue_types(project_key)
                print(f"📝 Found {len(issue_types)} issue types in project {project_key}")
            else:
                issue_types = await self.server.get_issue_types()
                print(f"📝 Found {len(issue_types)} issue types")
            return issue_types
        except Exception as e:
            print(f"❌ Error getting issue types: {e}")
            return []

    # ==================== PRIORITY & STATUS OPERATIONS ====================
    
    async def get_priorities(self) -> List[Priority]:
        """Get all priorities"""
        try:
            priorities = await self.server.get_priorities()
            print(f"⚡ Found {len(priorities)} priorities")
            return priorities
        except Exception as e:
            print(f"❌ Error getting priorities: {e}")
            return []
    
    async def get_statuses(self) -> List[Status]:
        """Get all statuses"""
        try:
            statuses = await self.server.get_statuses()
            print(f"📊 Found {len(statuses)} statuses")
            return statuses
        except Exception as e:
            print(f"❌ Error getting statuses: {e}")
            return []

    # ==================== ISSUE OPERATIONS ====================
    
    async def create_issue(self, issue_data: Dict[str, Any]) -> Optional[Issue]:
        """Create a new issue"""
        try:
            request = CreateIssueRequest(**issue_data)
            issue = await self.server.create_issue(request)
            print(f"✅ Created issue {issue.key}: {issue.summary}")
            return issue
        except Exception as e:
            print(f"❌ Error creating issue: {e}")
            return None
    
    async def get_issue(self, issue_key: str) -> Optional[Issue]:
        """Get specific issue by key"""
        try:
            issue = await self.server.get_issue(issue_key)
            print(f"📋 Issue {issue_key}: {issue.summary}")
            return issue
        except Exception as e:
            print(f"❌ Error getting issue {issue_key}: {e}")
            return None
    
    async def update_issue(self, issue_key: str, update_data: Dict[str, Any]) -> Optional[Issue]:
        """Update an existing issue"""
        try:
            request = UpdateIssueRequest(**update_data)
            issue = await self.server.update_issue(issue_key, request)
            print(f"✅ Updated issue {issue_key}")
            return issue
        except Exception as e:
            print(f"❌ Error updating issue {issue_key}: {e}")
            return None
    
    async def delete_issue(self, issue_key: str) -> bool:
        """Delete an issue"""
        try:
            await self.server.delete_issue(issue_key)
            print(f"✅ Deleted issue {issue_key}")
            return True
        except Exception as e:
            print(f"❌ Error deleting issue {issue_key}: {e}")
            return False
    
    async def search_issues(self, jql: str, max_results: int = 50) -> List[Issue]:
        """Search issues using JQL"""
        try:
            request = SearchIssuesRequest(jql=jql, max_results=max_results)
            issues = await self.server.search_issues(request)
            print(f"🔍 Found {len(issues)} issues matching JQL")
            return issues
        except Exception as e:
            print(f"❌ Error searching issues: {e}")
            return []

    # ==================== TRANSITION OPERATIONS ====================
    
    async def get_issue_transitions(self, issue_key: str) -> List[Transition]:
        """Get available transitions for an issue"""
        try:
            transitions = await self.server.get_issue_transitions(issue_key)
            print(f"🔄 Found {len(transitions)} transitions for {issue_key}")
            return transitions
        except Exception as e:
            print(f"❌ Error getting transitions for {issue_key}: {e}")
            return []
    
    async def transition_issue(self, issue_key: str, transition_id: str, comment: Optional[str] = None) -> bool:
        """Transition an issue to a new status"""
        try:
            await self.server.transition_issue(issue_key, transition_id, comment)
            print(f"✅ Transitioned issue {issue_key} to transition {transition_id}")
            return True
        except Exception as e:
            print(f"❌ Error transitioning issue {issue_key}: {e}")
            return False

    # ==================== COMMENT OPERATIONS ====================
    
    async def get_issue_comments(self, issue_key: str) -> List[Comment]:
        """Get comments for an issue"""
        try:
            comments = await self.server.get_issue_comments(issue_key)
            print(f"💬 Found {len(comments)} comments for {issue_key}")
            return comments
        except Exception as e:
            print(f"❌ Error getting comments for {issue_key}: {e}")
            return []
    
    async def add_comment(self, issue_key: str, comment_body: str) -> Optional[Comment]:
        """Add a comment to an issue"""
        try:
            comment = await self.server.add_comment(issue_key, comment_body)
            print(f"✅ Added comment to {issue_key}")
            return comment
        except Exception as e:
            print(f"❌ Error adding comment to {issue_key}: {e}")
            return None
    
    async def update_comment(self, issue_key: str, comment_id: str, comment_body: str) -> Optional[Comment]:
        """Update a comment"""
        try:
            comment = await self.server.update_comment(issue_key, comment_id, comment_body)
            print(f"✅ Updated comment {comment_id} on {issue_key}")
            return comment
        except Exception as e:
            print(f"❌ Error updating comment {comment_id}: {e}")
            return None
    
    async def delete_comment(self, issue_key: str, comment_id: str) -> bool:
        """Delete a comment"""
        try:
            await self.server.delete_comment(issue_key, comment_id)
            print(f"✅ Deleted comment {comment_id} from {issue_key}")
            return True
        except Exception as e:
            print(f"❌ Error deleting comment {comment_id}: {e}")
            return False

    # ==================== ATTACHMENT OPERATIONS ====================
    
    async def get_issue_attachments(self, issue_key: str) -> List[Attachment]:
        """Get attachments for an issue"""
        try:
            attachments = await self.server.get_issue_attachments(issue_key)
            print(f"📎 Found {len(attachments)} attachments for {issue_key}")
            return attachments
        except Exception as e:
            print(f"❌ Error getting attachments for {issue_key}: {e}")
            return []
    
    async def add_attachment(self, issue_key: str, file_path: str, filename: Optional[str] = None) -> Optional[Attachment]:
        """Add an attachment to an issue"""
        try:
            attachment = await self.server.add_attachment(issue_key, file_path, filename)
            print(f"✅ Added attachment to {issue_key}")
            return attachment
        except Exception as e:
            print(f"❌ Error adding attachment to {issue_key}: {e}")
            return None
    
    async def delete_attachment(self, attachment_id: str) -> bool:
        """Delete an attachment"""
        try:
            await self.server.delete_attachment(attachment_id)
            print(f"✅ Deleted attachment {attachment_id}")
            return True
        except Exception as e:
            print(f"❌ Error deleting attachment {attachment_id}: {e}")
            return False

    # ==================== UTILITY METHODS ====================
    
    def print_issue_summary(self, issue: Issue):
        """Print a formatted summary of an issue"""
        print(f"\n📋 {issue.key}: {issue.summary}")
        print(f"   Type: {issue.issue_type.name}")
        print(f"   Status: {issue.status.name}")
        print(f"   Priority: {issue.priority.name}")
        print(f"   Assignee: {issue.assignee.display_name if issue.assignee else 'Unassigned'}")
        print(f"   Reporter: {issue.reporter.display_name}")
        print(f"   Created: {issue.created}")
        if issue.description:
            print(f"   Description: {issue.description[:100]}...")
    
    def print_project_summary(self, project: Project):
        """Print a formatted summary of a project"""
        print(f"\n📋 {project.key}: {project.name}")
        print(f"   Type: {project.project_type}")
        print(f"   Lead: {project.lead.display_name}")
        print(f"   Description: {project.description[:100] if project.description else 'No description'}...")
    
    def print_user_summary(self, user: User):
        """Print a formatted summary of a user"""
        print(f"\n👤 {user.name}: {user.display_name}")
        print(f"   Email: {user.email_address}")
        print(f"   Active: {user.active}")
        if user.time_zone:
            print(f"   Timezone: {user.time_zone}")


# ==================== EXAMPLE USAGE ====================

async def example_usage():
    """Example of how to use the JiraOperations class"""
    
    # Initialize with your Jira credentials
    jira = JiraOperations(
        base_url="https://your-domain.atlassian.net",
        username="your-email@domain.com",
        api_token="your-api-token"
    )
    
    # Connect to Jira
    if not await jira.connect():
        return
    
    try:
        # Get all projects
        projects = await jira.get_projects()
        for project in projects[:3]:  # Show first 3
            jira.print_project_summary(project)
        
        # Get users from a specific project
        if projects:
            project_key = projects[0].key
            users = await jira.get_users(project_key)
            for user in users[:3]:  # Show first 3
                jira.print_user_summary(user)
        
        # Search for issues
        issues = await jira.search_issues("project = WEB AND status = 'To Do'", max_results=5)
        for issue in issues:
            jira.print_issue_summary(issue)
        
        # Create a new issue (example)
        # new_issue_data = {
        #     "project": {"key": "WEB"},
        #     "summary": "Test issue from script",
        #     "description": "This is a test issue created from the Jira operations script",
        #     "issue_type": {"name": "Task"},
        #     "priority": {"name": "Medium"}
        # }
        # new_issue = await jira.create_issue(new_issue_data)
        # if new_issue:
        #     jira.print_issue_summary(new_issue)
    
    finally:
        await jira.disconnect()


# ==================== COMMAND LINE INTERFACE ====================

async def main():
    """Command line interface for Jira operations"""
    if len(sys.argv) < 2:
        print("Usage: python jira_operations.py <command> [args...]")
        print("\nAvailable commands:")
        print("  projects                    - List all projects")
        print("  project <key>               - Get specific project")
        print("  users [project_key]         - List users (optionally filtered by project)")
        print("  dump-users-json [project_key] - Print users as JSON to stdout")
        print("  user <username>             - Get specific user")
        print("  search-users <query>        - Search users")
        print("  issue-types [project_key]   - List issue types")
        print("  priorities                  - List priorities")
        print("  statuses                    - List statuses")
        print("  issue <key>                 - Get specific issue")
        print("  search <jql>                - Search issues with JQL")
        print("  transitions <issue_key>     - Get available transitions for issue")
        print("  comments <issue_key>        - Get comments for issue")
        print("  attachments <issue_key>     - Get attachments for issue")
        print("  example                     - Run example usage")
        return
    
    # You'll need to set these environment variables or modify this section
    base_url = os.getenv("JIRA_BASE_URL", "https://your-domain.atlassian.net")
    username = os.getenv("JIRA_USERNAME", "your-email@domain.com")
    api_token = os.getenv("JIRA_API_TOKEN", "your-api-token")
    
    jira = JiraOperations(base_url, username, api_token)
    
    if not await jira.connect():
        return
    
    try:
        command = sys.argv[1].lower()
        
        if command == "projects":
            projects = await jira.get_projects()
            for project in projects:
                jira.print_project_summary(project)
        
        elif command == "project" and len(sys.argv) > 2:
            project = await jira.get_project(sys.argv[2])
            if project:
                jira.print_project_summary(project)
        
        elif command == "users":
            project_key = sys.argv[2] if len(sys.argv) > 2 else None
            users = await jira.get_users(project_key)
            for user in users:
                jira.print_user_summary(user)

        elif command == "dump-users-json":
            import json as _json
            project_key = sys.argv[2] if len(sys.argv) > 2 else None
            users = await jira.get_users(project_key)
            payload = [
                {
                    "account_id": getattr(u, "account_id", None) or getattr(u, "id", None) or "",
                    "display_name": getattr(u, "display_name", None) or getattr(u, "name", None) or "",
                    "email_address": getattr(u, "email_address", None) or getattr(u, "email", None) or None,
                }
                for u in users
            ]
            print(_json.dumps(payload, ensure_ascii=False))
        
        elif command == "user" and len(sys.argv) > 2:
            user = await jira.get_user(sys.argv[2])
            if user:
                jira.print_user_summary(user)
        
        elif command == "search-users" and len(sys.argv) > 2:
            users = await jira.search_users(sys.argv[2])
            for user in users:
                jira.print_user_summary(user)
        
        elif command == "issue-types":
            project_key = sys.argv[2] if len(sys.argv) > 2 else None
            issue_types = await jira.get_issue_types(project_key)
            for it in issue_types:
                print(f"📝 {it.name}: {it.description}")
        
        elif command == "priorities":
            priorities = await jira.get_priorities()
            for priority in priorities:
                print(f"⚡ {priority.name}: {priority.description}")
        
        elif command == "statuses":
            statuses = await jira.get_statuses()
            for status in statuses:
                print(f"📊 {status.name}: {status.description}")
        
        elif command == "issue" and len(sys.argv) > 2:
            issue = await jira.get_issue(sys.argv[2])
            if issue:
                jira.print_issue_summary(issue)
        
        elif command == "search" and len(sys.argv) > 2:
            jql = " ".join(sys.argv[2:])
            issues = await jira.search_issues(jql)
            for issue in issues:
                jira.print_issue_summary(issue)
        
        elif command == "transitions" and len(sys.argv) > 2:
            transitions = await jira.get_issue_transitions(sys.argv[2])
            for transition in transitions:
                print(f"🔄 {transition.name}: {transition.description}")
        
        elif command == "comments" and len(sys.argv) > 2:
            comments = await jira.get_issue_comments(sys.argv[2])
            for comment in comments:
                print(f"💬 {comment.author.display_name}: {comment.body[:100]}...")
        
        elif command == "attachments" and len(sys.argv) > 2:
            attachments = await jira.get_issue_attachments(sys.argv[2])
            for attachment in attachments:
                print(f"📎 {attachment.filename}: {attachment.size} bytes")
        
        elif command == "example":
            await example_usage()
        
        else:
            print(f"Unknown command: {command}")
    
    finally:
        await jira.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
