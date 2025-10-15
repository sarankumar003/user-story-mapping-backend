"""
JSON-driven Jira issue creator.

Usage examples:
  - Generate a template JSON:
      python scripts/jira_from_json.py --generate issues.sample.json

  - Create issues from a JSON file using your existing env file:
      python scripts/jira_from_json.py --input issues.json --env-file C:/Users/sarank/.cursor/mcp-atlassian.env

JSON format (single issue or array):
{
  "project": "NT",
  "issuetype": "Story",
  "summary": "task2",
  "description": "Optional description",
  "parent": "NT-1",               # For team-managed: Story under Epic
  "assignee": "user@email.com",    # Optional
  "priority": "High",              # Optional
  "labels": ["label1", "label2"]   # Optional
}

Notes:
- For company-managed projects, if you need Epic Link instead of parent, pass --epic-field-id (e.g., customfield_10014) and include "epic": "EPIC-KEY" in the JSON.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

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


def read_env_file(env_file_path: str) -> Dict[str, str]:
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
    env = read_env_file(env_file)
    base_url = env.get("JIRA_URL", "").rstrip("/")
    username = env.get("JIRA_USERNAME", "")
    token = env.get("JIRA_API_TOKEN", "")
    if not base_url or not username or not token:
        raise ValueError("JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN must be set in env file")
    return JiraAuth(base_url=base_url, username=username, api_token=token)


def http_post(url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    payload = json.dumps(body).encode("utf-8")
    if requests:
        resp = requests.post(url, headers=headers, data=payload, timeout=30)
        return resp.status_code, (resp.json() if resp.content else {})
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
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


def create_epic(auth: JiraAuth, epic_data: Dict[str, Any]) -> str:
    """Create an epic and return its key."""
    fields = {
        "project": {"key": epic_data["project"]},
        "issuetype": {"name": "Epic"},
        "summary": epic_data["summary"],
    }
    
    description = epic_data.get("description")
    if description:
        if isinstance(description, str):
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
            }
        else:
            fields["description"] = description
    
    # Get available fields for epic to check if epic name field exists
    available_fields = get_issue_metadata(auth, epic_data["project"], "Epic")
    
    # Epic name field (usually customfield_10011) - only set if available
    epic_name = epic_data.get("epic_name", epic_data["summary"])
    if "customfield_10011" in available_fields:
        fields["customfield_10011"] = epic_name
    
    url = f"{auth.base_url}/rest/api/3/issue"
    code, data = http_post(url, headers=auth.build_headers(), body={"fields": fields})
    if code not in (200, 201):
        raise RuntimeError(f"Create epic failed ({code}): {json.dumps(data, ensure_ascii=False)}")
    key = data.get("key")
    if not key:
        raise RuntimeError(f"Create epic returned no key: {data}")
    return key


def find_epic_by_name(auth: JiraAuth, project: str, epic_name: str) -> str | None:
    """Find epic by name in project. Returns key if found, None otherwise."""
    jql = f'project = {project} AND issuetype = Epic AND summary = "{epic_name}"'
    url = f"{auth.base_url}/rest/api/3/search?jql={jql}&maxResults=1&fields=key,summary"
    code, data = http_post(url, headers=auth.build_headers(), body={})
    if code == 200 and data.get("issues"):
        for issue in data["issues"]:
            if issue["fields"]["summary"] == epic_name:
                return issue["key"]
    return None


def get_issue_metadata(auth: JiraAuth, project: str, issue_type: str) -> Dict[str, Any]:
    """Get issue creation metadata to validate available fields."""
    url = f"{auth.base_url}/rest/api/3/issue/createmeta?projectKeys={project}&issuetypeNames={issue_type}&expand=projects.issuetypes.fields"
    code, data = http_post(url, headers=auth.build_headers(), body={})
    if code == 200 and data.get("projects"):
        project_data = data["projects"][0]
        if project_data.get("issuetypes"):
            return project_data["issuetypes"][0].get("fields", {})
    return {}


def create_issue(auth: JiraAuth, issue: Dict[str, Any], epic_field_id: str | None = None) -> str:
    fields: Dict[str, Any] = {
        "project": {"key": issue["project"]},
        "issuetype": {"name": issue["issuetype"]},
        "summary": issue["summary"],
    }

    # Get available fields for validation
    available_fields = get_issue_metadata(auth, issue["project"], issue["issuetype"])

    description = issue.get("description")
    if description:
        # Convert plain text to Atlassian Document Format (ADF)
        if isinstance(description, str):
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            }
        else:
            # Assume it's already in ADF format
            fields["description"] = description

    labels = issue.get("labels")
    if isinstance(labels, list) and labels and "labels" in available_fields:
        fields["labels"] = labels

    assignee = issue.get("assignee")
    if assignee and assignee.strip() and "assignee" in available_fields:
        fields["assignee"] = {"name": assignee, "accountId": assignee}

    priority = issue.get("priority")
    if priority and priority.strip() and "priority" in available_fields:
        fields["priority"] = {"name": priority}

    # Team-managed: Story under Epic via parent
    parent_key = issue.get("parent")
    if parent_key:
        # Always try to set parent, even if not in available_fields (some projects don't show it in metadata)
        fields["parent"] = {"key": parent_key}

    # Company-managed: Epic Link via custom field
    epic_key = issue.get("epic")
    if epic_key and epic_field_id and epic_field_id in available_fields:
        fields[epic_field_id] = epic_key

    # Arbitrary custom fields passthrough (only if they exist)
    custom = issue.get("customfields") or {}
    if isinstance(custom, dict):
        for k, v in custom.items():
            if k in available_fields:
                fields[k] = v

    url = f"{auth.base_url}/rest/api/3/issue"
    payload = {"fields": fields}
    print(f"Creating {issue['issuetype']}: {issue['summary']} with fields: {json.dumps(payload, indent=2)}")
    code, data = http_post(url, headers=auth.build_headers(), body=payload)
    if code not in (200, 201):
        raise RuntimeError(f"Create issue failed ({code}): {json.dumps(data, ensure_ascii=False)}")
    key = data.get("key")
    if not key:
        raise RuntimeError(f"Create issue returned no key: {data}")
    return key


def parse_issues_json(path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse JSON and separate epics from issues."""
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    
    if isinstance(obj, dict):
        obj = [obj]
    elif not isinstance(obj, list):
        raise ValueError("Input JSON must be an object or array of objects")
    
    epics = []
    issues = []
    
    for item in obj:
        if item.get("issuetype") == "Epic":
            epics.append(validate_epic_dict(item))
        else:
            issues.append(validate_issue_dict(item))
    
    return epics, issues


def validate_epic_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    required = ["project", "summary"]
    missing = [r for r in required if not item.get(r)]
    if missing:
        raise ValueError(f"Missing required fields for epic: {', '.join(missing)}")
    return item


def validate_issue_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    required = ["project", "issuetype", "summary"]
    missing = [r for r in required if not item.get(r)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    return item


def write_template(path: str) -> None:
    sample = [
        {
            "project": "NT",
            "issuetype": "Epic",
            "summary": "User Authentication Epic",
            "description": "Epic for all authentication-related features",
            "epic_name": "Auth Epic"
        },
        {
            "project": "NT", 
            "issuetype": "Epic",
            "summary": "Payment Processing Epic",
            "description": "Epic for payment and billing features",
            "epic_name": "Payment Epic"
        },
        {
            "project": "NT",
            "issuetype": "Story",
            "summary": "Implement user login",
            "description": "Create login form with email/password validation",
            "epic_name": "User Authentication Epic",
            "assignee": "",
            "labels": ["frontend", "auth"]
        },
        {
            "project": "NT",
            "issuetype": "Story", 
            "summary": "Add password reset functionality",
            "description": "Allow users to reset forgotten passwords via email",
            "epic_name": "User Authentication Epic",
            "assignee": "",
            "labels": ["backend", "auth"]
        },
        {
            "project": "NT",
            "issuetype": "Subtask",
            "summary": "Design login UI mockups",
            "description": "Create wireframes and mockups for login interface",
            "parent_story": "Implement user login",
            "assignee": "",
            "labels": ["design"]
        },
        {
            "project": "NT",
            "issuetype": "Story",
            "summary": "Process credit card payments",
            "description": "Integrate with payment gateway for credit card processing",
            "epic_name": "Payment Processing Epic", 
            "assignee": "",
            "labels": ["backend", "payment"]
        },
        {
            "project": "NT",
            "issuetype": "Subtask",
            "summary": "Set up Stripe integration",
            "description": "Configure Stripe API keys and webhook endpoints",
            "parent_story": "Process credit card payments",
            "assignee": "",
            "labels": ["integration", "payment"]
        }
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sample, f, indent=2)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create Jira issues from JSON")
    parser.add_argument("--input", help="Path to JSON file with one or more issues")
    parser.add_argument("--generate", help="Write a template JSON to the given path and exit")
    parser.add_argument("--env-file", default=os.path.expanduser("~/.cursor/mcp-atlassian.env"), help="Path to env file with JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN")
    parser.add_argument("--epic-field-id", help="Epic Link field id for company-managed projects (e.g. customfield_10014)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.generate:
        write_template(args.generate)
        print(f"Wrote template: {args.generate}")
        return 0

    if not args.input:
        print("--input is required unless using --generate", file=sys.stderr)
        return 2

    auth = load_auth(args.env_file)
    epics, issues = parse_issues_json(args.input)

    # Create epics first and track their keys
    epic_keys: Dict[str, str] = {}  # epic_name -> epic_key
    created: List[str] = []
    
    # Create epics
    print(f"Processing {len(epics)} epics...")
    for epic in epics:
        try:
            epic_name = epic["summary"]
            # Check if epic already exists
            existing_key = find_epic_by_name(auth, epic["project"], epic_name)
            if existing_key:
                epic_keys[epic_name] = existing_key
                print(f"Found existing epic: {existing_key} ({epic_name})")
            else:
                key = create_epic(auth, epic)
                epic_keys[epic_name] = key
                created.append(key)
                print(f"Created epic: {key} ({epic_name})")
        except Exception as e:
            print(f"ERROR creating epic '{epic.get('summary','')}' -> {e}", file=sys.stderr)
            return 1

    # Create issues and link to epics
    print(f"Processing {len(issues)} issues...")
    print(f"Available epic keys: {epic_keys}")
    
    # Track created stories for subtask linking
    story_keys: Dict[str, str] = {}  # story_summary -> story_key
    
    for issue in issues:
        try:
            # Handle epic linking
            epic_name = issue.get("epic_name")
            if epic_name and epic_name in epic_keys:
                issue["parent"] = epic_keys[epic_name]
                print(f"Linking {issue['summary']} to epic {epic_keys[epic_name]}")
            
            # Handle subtask parent linking
            parent_story = issue.get("parent_story")
            if parent_story and issue.get("issuetype") == "Subtask":
                # First check if we just created the parent story
                if parent_story in story_keys:
                    issue["parent"] = story_keys[parent_story]
                    print(f"Linking subtask {issue['summary']} to newly created story {story_keys[parent_story]}")
                else:
                    # Find parent story by summary
                    jql = f'project = {issue["project"]} AND issuetype = Story AND summary = "{parent_story}"'
                    url = f"{auth.base_url}/rest/api/3/search?jql={jql}&maxResults=1&fields=key,summary"
                    code, data = http_post(url, headers=auth.build_headers(), body={})
                    if code == 200 and data.get("issues"):
                        for story_issue in data["issues"]:
                            if story_issue["fields"]["summary"] == parent_story:
                                issue["parent"] = story_issue["key"]
                                print(f"Linking subtask {issue['summary']} to existing story {story_issue['key']}")
                                break
                    else:
                        print(f"WARNING: Parent story '{parent_story}' not found for subtask '{issue['summary']}'", file=sys.stderr)
            
            key = create_issue(auth, issue, epic_field_id=args.epic_field_id)
            created.append(key)
            
            # Track story keys for subtask linking
            if issue.get("issuetype") == "Story":
                story_keys[issue["summary"]] = key
            
            print(f"Created {issue['issuetype'].lower()}: {key} ({issue['summary']})")
        except Exception as e:
            print(f"ERROR creating issue for summary='{issue.get('summary','')}' -> {e}", file=sys.stderr)
            return 1

    if not created:
        print("No issues created", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


