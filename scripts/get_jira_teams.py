"""
Jira Teams and People Fetcher

This script fetches all active users and their team information from Jira
and saves it to a JSON file for use in issue assignment workflows.

Usage:
    python scripts/get_jira_teams.py --env-file C:/Users/sarank/.cursor/mcp-atlassian.env --output teams.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - fallback to stdlib
    requests = None  # type: ignore
    import urllib.request
    import urllib.error


@dataclass
class JiraAuth:
    base_url: str
    username: str
    api_token: str

    def build_headers(self) -> Dict[str, str]:
        credentials = f"{self.username}:{self.api_token}".encode("ascii")
        b64 = base64.b64encode(credentials).decode("ascii")
        return {
            "Authorization": f"Basic {b64}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }


@dataclass
class TeamMember:
    display_name: str
    account_id: str
    email_address: str | None
    active: bool
    teams: List[str]
    projects: List[str]


def read_env_file(env_file_path: str) -> Dict[str, str]:
    """Read environment variables from file."""
    if not os.path.exists(env_file_path):
        raise FileNotFoundError(f"Env file not found: {env_file_path}")
    env: Dict[str, str] = {}
    with open(env_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def load_auth(env_file: str) -> JiraAuth:
    """Load Jira authentication from env file."""
    env = read_env_file(env_file)
    base_url = env.get("JIRA_URL", "").rstrip("/")
    username = env.get("JIRA_USERNAME", "")
    token = env.get("JIRA_API_TOKEN", "")
    if not base_url or not username or not token:
        raise ValueError("JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN must be set in env file")
    return JiraAuth(base_url=base_url, username=username, api_token=token)


def http_get(url: str, headers: Dict[str, str]) -> tuple[int, Dict[str, Any]]:
    """Make HTTP GET request and return status code and JSON response."""
    if requests:
        resp = requests.get(url, headers=headers, timeout=30)
        return resp.status_code, (resp.json() if resp.content else {})
    
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # type: ignore
            content = resp.read().decode("utf-8")
            return resp.getcode(), (json.loads(content) if content else {})
    except urllib.error.HTTPError as e:  # type: ignore
        content = e.read().decode("utf-8")
        try:
            return e.code, json.loads(content)
        except Exception:
            return e.code, {"error": content}


def get_all_users(auth: JiraAuth) -> List[Dict[str, Any]]:
    """Get all users from Jira."""
    url = f"{auth.base_url}/rest/api/3/users/search?maxResults=1000"
    code, data = http_get(url, auth.build_headers())
    if code != 200:
        raise RuntimeError(f"Failed to get users ({code}): {json.dumps(data, ensure_ascii=False)}")
    return data


def get_projects(auth: JiraAuth) -> List[Dict[str, Any]]:
    """Get all projects from Jira."""
    url = f"{auth.base_url}/rest/api/3/project"
    code, data = http_get(url, auth.build_headers())
    if code != 200:
        raise RuntimeError(f"Failed to get projects ({code}): {json.dumps(data, ensure_ascii=False)}")
    return data


def get_user_groups(auth: JiraAuth, account_id: str) -> List[str]:
    """Get groups/teams for a specific user."""
    url = f"{auth.base_url}/rest/api/3/user?accountId={account_id}&expand=groups"
    code, data = http_get(url, auth.build_headers())
    if code != 200:
        return []
    
    groups = data.get("groups", {}).get("items", [])
    return [group["name"] for group in groups]


def get_user_projects(auth: JiraAuth, account_id: str) -> List[str]:
    """Get projects where user has permissions."""
    try:
        # Try to get user's project permissions
        url = f"{auth.base_url}/rest/api/3/user/permission/search?accountId={account_id}"
        code, data = http_get(url, auth.build_headers())
        if code == 200 and data.get("permissions"):
            projects = set()
            for perm in data["permissions"]:
                if perm.get("project"):
                    projects.add(perm["project"]["name"])
            return list(projects)
    except Exception:
        pass
    
    # Fallback: check if user is lead of any projects
    projects = get_projects(auth)
    user_projects = []
    for project in projects:
        if project.get("lead", {}).get("accountId") == account_id:
            user_projects.append(project["name"])
    
    return user_projects


def fetch_teams_and_people(auth: JiraAuth) -> Dict[str, Any]:
    """Fetch all teams and people from Jira."""
    print("Fetching users...")
    users = get_all_users(auth)
    
    print("Fetching projects...")
    projects = get_projects(auth)
    
    print("Processing team members...")
    team_members: List[TeamMember] = []
    
    for user in users:
        if not user.get("active", False) or user.get("accountType") != "atlassian":
            continue
        
        account_id = user["accountId"]
        display_name = user["displayName"]
        email_address = user.get("emailAddress")
        
        print(f"  Processing {display_name}...")
        
        # Get user's groups/teams
        teams = get_user_groups(auth, account_id)
        
        # Get user's projects
        user_projects = get_user_projects(auth, account_id)
        
        team_member = TeamMember(
            display_name=display_name,
            account_id=account_id,
            email_address=email_address,
            active=user.get("active", False),
            teams=teams,
            projects=user_projects
        )
        team_members.append(team_member)
    
    # Organize by teams
    teams_data: Dict[str, List[Dict[str, Any]]] = {}
    for member in team_members:
        if not member.teams:
            # Users without teams go to "No Team"
            team_name = "No Team"
        else:
            # Add to each team they belong to
            for team in member.teams:
                if team not in teams_data:
                    teams_data[team] = []
                teams_data[team].append({
                    "display_name": member.display_name,
                    "account_id": member.account_id,
                    "email_address": member.email_address,
                    "projects": member.projects
                })
    
    # If no teams found, organize by projects
    if not teams_data:
        print("No teams found, organizing by projects...")
        for member in team_members:
            if not member.projects:
                project_name = "No Project"
            else:
                project_name = member.projects[0]  # Use first project
            
            if project_name not in teams_data:
                teams_data[project_name] = []
            teams_data[project_name].append({
                "display_name": member.display_name,
                "account_id": member.account_id,
                "email_address": member.email_address,
                "projects": member.projects
            })
    
    return {
        "metadata": {
            "total_users": len(team_members),
            "total_teams": len(teams_data),
            "generated_at": "unknown"
        },
        "teams": teams_data,
        "all_users": [
            {
                "display_name": member.display_name,
                "account_id": member.account_id,
                "email_address": member.email_address,
                "teams": member.teams,
                "projects": member.projects
            }
            for member in team_members
        ]
    }


def main(argv: list[str] | None = None) -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description="Fetch Jira teams and people")
    parser.add_argument("--env-file", default=os.path.expanduser("~/.cursor/mcp-atlassian.env"), 
                       help="Path to env file with JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN")
    parser.add_argument("--output", default="jira_teams.json", 
                       help="Output JSON file path")
    args = parser.parse_args(argv if argv is not None else None)
    
    try:
        auth = load_auth(args.env_file)
        teams_data = fetch_teams_and_people(auth)
        
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(teams_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Successfully saved teams data to {args.output}")
        print(f"📊 Found {teams_data['metadata']['total_users']} users across {teams_data['metadata']['total_teams']} teams")
        
        # Print summary
        print("\n📋 Teams Summary:")
        for team_name, members in teams_data["teams"].items():
            print(f"  {team_name}: {len(members)} members")
            for member in members:
                print(f"    - {member['display_name']} ({member['account_id']})")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
