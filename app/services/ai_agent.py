"""
AI Agent Service
Handles AI-powered document summarization and requirements decomposition
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import re
import uuid
from openai import OpenAI
from app.core.config import settings
from app.models.document import DocumentSummary
from app.models.requirement import Epic, Story, Subtask, RequirementsDecomposition, TaskStatus, Priority

logger = logging.getLogger(__name__)


class AIAgent:
    """AI agent for document processing and requirements decomposition"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
    
    async def generate_summary(self, document_text: str) -> DocumentSummary:
        """Generate BRD summary using AI"""
        
        prompt = f"""
        Analyze the following Business Requirements Document (BRD) and extract key information in a structured format.
        
        Document Text:
        {document_text}
        
        Please provide a comprehensive summary with the following structure:
        1. Project Name: Extract the main project name
        2. Project Description: Brief overview of the project
        3. Objectives: List of main project objectives
        4. Scope: List of what's included and excluded
        5. Stakeholders: List of key stakeholders
        6. Key Features: List of main features/functionalities
        7. Technical Requirements: List of technical specifications
        8. Timeline Estimate: Estimated project timeline
        9. Risks: List of identified risks
        10. Assumptions: List of project assumptions
        
        Return the response as a JSON object with the following structure:
        {{
            "project_name": "string",
            "project_description": "string",
            "objectives": ["string1", "string2"],
            "scope": ["string1", "string2"],
            "stakeholders": ["string1", "string2"],
            "key_features": ["string1", "string2"],
            "technical_requirements": ["string1", "string2"],
            "timeline_estimate": "string",
            "risks": ["string1", "string2"],
            "assumptions": ["string1", "string2"]
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert business analyst who specializes in analyzing BRD documents and extracting structured information. Always respond with valid JSON only, no additional text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            content = response.choices[0].message.content
            logger.info(f"Raw AI Response: {repr(content)}")  # Use repr to see escape characters
            
            # Improved JSON cleaning
            cleaned_content = self._clean_and_validate_json(content)
            logger.info(f"Cleaned JSON: {cleaned_content[:200]}...")
            
            summary_data = json.loads(cleaned_content)
            # Normalize potential schema variations from the model
            summary_data = self._normalize_summary_payload(summary_data)
            
            return DocumentSummary(**summary_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Raw AI response: {repr(content)}")
            logger.error(f"Cleaned content: {repr(cleaned_content)}")
            # Return a default summary if JSON parsing fails
            return DocumentSummary(
                project_name="Unknown Project",
                project_description="Failed to parse AI response",
                objectives=["Parse AI response"],
                scope=["Document processing"],
                stakeholders=["Unknown"],
                key_features=["Error handling"],
                technical_requirements=["Fix JSON parsing"],
                timeline_estimate="Unknown",
                risks=["AI response parsing failed"],
                assumptions=["Document contains valid BRD content"]
            )
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise

    def _clean_and_validate_json(self, content: str) -> str:
        """
        Improved JSON cleaning and validation
        """
        if not content:
            return "{}"
        
        # Log the original content with all characters visible
        logger.debug(f"Original content (repr): {repr(content)}")
        
        # Remove any leading/trailing whitespace
        content = content.strip()
        
        # Remove markdown code fences if present
        if content.startswith("```"):
            # Find the first opening brace after ```
            start_idx = content.find("{")
            # Find the last closing brace before ```
            end_marker = content.rfind("```")
            if end_marker > start_idx:
                end_idx = content.rfind("}", 0, end_marker) + 1
            else:
                end_idx = content.rfind("}") + 1
            
            if start_idx != -1 and end_idx > start_idx:
                content = content[start_idx:end_idx]
        
        # If we still don't have proper JSON structure, try to extract it
        if not content.startswith("{"):
            start_idx = content.find("{")
            if start_idx != -1:
                content = content[start_idx:]
        
        if not content.endswith("}"):
            end_idx = content.rfind("}")
            if end_idx != -1:
                content = content[:end_idx + 1]
        
        # Basic JSON validation attempt
        try:
            # Try to parse it first
            json.loads(content)
            return content
        except json.JSONDecodeError as e:
            logger.warning(f"JSON validation failed: {e}")
            
            # Try to fix common issues
            # Replace any problematic characters that might have been escaped incorrectly
            content = content.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ')
            
            # Remove any trailing commas before closing brackets/braces
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            
            # Try parsing again
            try:
                json.loads(content)
                return content
            except json.JSONDecodeError:
                logger.error(f"Could not fix JSON: {repr(content)}")
                return "{}"

    def _normalize_summary_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce common LLM variations to match DocumentSummary schema.
        - scope may arrive as { in_scope: [], out_of_scope: [] } → combine to flat list
        - list fields may come as string → wrap into list
        - ensure required keys exist with sensible defaults
        """
        def ensure_list(value: Any) -> List[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(v) for v in value]
            return [str(value)]

        normalized: Dict[str, Any] = {}

        normalized["project_name"] = str(data.get("project_name") or "Unknown Project")
        normalized["project_description"] = str(data.get("project_description") or "")

        normalized["objectives"] = ensure_list(data.get("objectives"))

        scope_val = data.get("scope")
        if isinstance(scope_val, dict):
            in_scope = ensure_list(scope_val.get("in_scope"))
            out_scope = ensure_list(scope_val.get("out_of_scope"))
            # Prefix out-of-scope items so the meaning is preserved
            out_scope = [f"Out of scope: {item}" for item in out_scope]
            normalized["scope"] = in_scope + out_scope
        else:
            normalized["scope"] = ensure_list(scope_val)

        normalized["stakeholders"] = ensure_list(data.get("stakeholders"))
        normalized["key_features"] = ensure_list(data.get("key_features"))
        normalized["technical_requirements"] = ensure_list(data.get("technical_requirements"))
        normalized["timeline_estimate"] = str(data.get("timeline_estimate") or "Unknown")
        normalized["risks"] = ensure_list(data.get("risks"))
        normalized["assumptions"] = ensure_list(data.get("assumptions"))

        return normalized
    
    async def decompose_requirements(self, summary: DocumentSummary) -> Tuple[RequirementsDecomposition, str]:
        """AI-powered decomposition with comprehensive project management perspective.

        Returns a tuple of (RequirementsDecomposition, raw_response_text).
        """

        def coerce_priority(value: Any) -> Priority:
            if isinstance(value, Priority):
                return value
            try:
                return Priority(str(value).strip().title())
            except Exception:
                return Priority.MEDIUM

        def coerce_status(value: Any) -> TaskStatus:
            if isinstance(value, TaskStatus):
                return value
            mapping = {
                "todo": TaskStatus.TODO,
                "to do": TaskStatus.TODO,
                "in progress": TaskStatus.IN_PROGRESS,
                "done": TaskStatus.DONE,
            }
            return mapping.get(str(value).strip().lower(), TaskStatus.TODO)

        def coerce_int(value: Any, default: int = 0) -> int:
            try:
                if value is None:
                    return default
                if isinstance(value, (int, float)):
                    return int(value)
                s = str(value).strip().lower().replace("h", "")
                return int(float(s))
            except Exception:
                return default

        def coerce_list_of_strings(value: Any) -> List[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(v) for v in value]
            return [str(value)]

        # Comprehensive system prompt for project management perspective
        system_prompt = """You are a well experienced project manager and Jira expert who can breakdown the action items and decompose the overall requirements into epics/stories/subtasks efficiently. So that the development team and other teams can work seamlessly to produce the proper results on time. 

Remember the board will accommodate all the teams like frontend/backend/data engineers/devops/it/hr/legal/etc. So all the action items involved in completing the client requirement should be captured.

Key Guidelines:
1. Prioritization Criteria: Consider business value, user impact, technical dependencies, and risk factors
2. Story Point Estimation: Use Fibonacci sequence (1, 2, 3, 5, 8, 13, 21) for story points
3. Definition of Done: Include testing, documentation, code review, and deployment criteria
4. Cross-team Coordination: Identify handoffs between teams and create coordination tasks
5. All tickets should be created as "To Do" status only
6. Include non-technical tasks: legal reviews, HR approvals, compliance checks, etc.
7. Consider infrastructure, security, and operational requirements
8. Break down complex features into manageable, testable units

Always respond with valid JSON only, no additional text."""

        # Enhanced sample output format with cross-team considerations
        features_text = ", ".join(summary.key_features or [])
        exemplar = {
            "epics": [
                {
                    "id": "epic_1",
                    "title": "User Authentication & Authorization",
                    "description": "Complete user authentication system with role-based access control, including frontend UI, backend APIs, database design, security implementation, and legal compliance",
                    "priority": "High",
                    "estimated_hours": 120,
                    "status": "To Do",
                    "stories": [
                        {
                            "id": "story_1",
                            "title": "Frontend Login/Registration UI",
                            "description": "Create responsive login and registration forms with validation, error handling, and accessibility compliance",
                            "acceptance_criteria": [
                                "Email and password validation with real-time feedback",
                                "Error messages displayed clearly to users",
                                "Mobile-responsive design",
                                "Accessibility compliance (WCAG 2.1 AA)",
                                "Integration with backend authentication API"
                            ],
                            "priority": "High",
                            "estimated_hours": 24,
                            "status": "To Do",
                            "subtasks": [
                                {
                                    "id": "subtask_1", 
                                    "title": "Design Login Form Components", 
                                    "description": "Create reusable form components with validation", 
                                    "priority": "High", 
                                    "estimated_hours": 8, 
                                    "status": "To Do"
                                },
                                {
                                    "id": "subtask_2", 
                                    "title": "Implement Form Validation", 
                                    "description": "Add client-side validation with error handling", 
                                    "priority": "Medium", 
                                    "estimated_hours": 6, 
                                    "status": "To Do"
                                }
                            ]
                        }
                    ]
                }
            ],
            "total_estimated_hours": 120,
            "timeline_weeks": 6
        }
        
        prompt = f"""
        Based on the following BRD summary, produce a comprehensive decomposition that covers all aspects of the project including technical, non-technical, and cross-team coordination tasks.

        Project: {summary.project_name}
        Description: {summary.project_description}
        Objectives: {', '.join(summary.objectives or [])}
        Key Features: {features_text}
        Technical Requirements: {', '.join(summary.technical_requirements or [])}
        Stakeholders: {', '.join(summary.stakeholders or [])}
        Risks: {', '.join(summary.risks or [])}
        Assumptions: {', '.join(summary.assumptions or [])}

        Return exactly one JSON object with keys: epics (array), total_estimated_hours (number), timeline_weeks (number).
        
        Each epic must include:
        - id: unique identifier
        - title: descriptive epic name
        - description: comprehensive description including business justification
        - priority: Low, Medium, High, or Critical
        - estimated_hours: total hours for the epic
        - status: "To Do" (all tickets should be To Do)
        - stories: array of user stories
        
        Each story must include:
        - id: unique identifier
        - title: user story title
        - description: detailed description
        - acceptance_criteria: array of specific, testable criteria
        - priority: Low, Medium, High, or Critical
        - estimated_hours: story point estimation
        - status: "To Do"
        - subtasks: array of technical subtasks
        
        Each subtask must include:
        - id: unique identifier
        - title: specific task title
        - description: detailed technical description
        - priority: Low, Medium, High, or Critical
        - estimated_hours: specific time estimate
        - status: "To Do"

        Consider all teams: Frontend, Backend, Data Engineers, DevOps, IT, HR, Legal, QA, UX/UI, Product Management, etc.
        Include cross-team coordination, handoffs, reviews, approvals, and dependencies.
        All tickets must be created as "To Do" status only.
        """

        content = "{}"
        raw_response = ""
        
        # Retry up to 3 times for better robustness
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=8000,
                    response_format={"type": "json_object"},  # Force JSON response
                )
                raw_response = response.choices[0].message.content or "{}"
                logger.info(f"Raw AI Response (attempt {attempt + 1}): {repr(raw_response[:200])}...")
                
                if raw_response and raw_response.strip():
                    # Clean and validate the JSON
                    content = self._clean_and_validate_json(raw_response)
                    
                    # Test if it parses correctly
                    json.loads(content)  # This will raise an exception if invalid
                    logger.info(f"Successfully parsed JSON on attempt {attempt + 1}")
                    break
                    
            except json.JSONDecodeError as je:
                logger.warning(f"JSON parse error (attempt {attempt+1}): {str(je)}")
                if attempt == 2:  # Last attempt
                    logger.error(f"Final JSON parse failure: {repr(raw_response)}")
            except Exception as e:
                logger.error(f"OpenAI error (attempt {attempt+1}) during decomposition: {str(e)}")
                if attempt == 2:  # Last attempt
                    raw_response = "{}"
                    content = "{}"

        # Parse the final JSON
        try:
            data = json.loads(content)
            logger.info("Successfully loaded JSON data from AI response")
        except Exception as e:
            logger.error(f"Final JSON parse error: {str(e)} | content={repr(content[:500])}")
            data = {"epics": [], "total_estimated_hours": 0, "timeline_weeks": 0}

        # Build Pydantic models safely, tolerating partial/malformed items
        epics: List[Epic] = []
        total_estimated = 0
        source_epics = data.get("epics", []) or []
        
        logger.info(f"Processing {len(source_epics)} epics from AI response")
        
        for epic_idx, epic_obj in enumerate(source_epics):
            try:
                stories: List[Story] = []
                for story_idx, story_obj in enumerate(epic_obj.get("stories", []) or []):
                    try:
                        subtasks: List[Subtask] = []
                        for sub_idx, sub_obj in enumerate(story_obj.get("subtasks", []) or []):
                            try:
                                subtasks.append(
                                    Subtask(
                                        id=sub_obj.get("id") or f"subtask_{epic_idx}_{story_idx}_{sub_idx}",
                                        title=sub_obj.get("title") or "Subtask",
                                        description=sub_obj.get("description") or "",
                                        priority=coerce_priority(sub_obj.get("priority")),
                                        estimated_hours=coerce_int(sub_obj.get("estimated_hours"), 0),
                                        status=coerce_status(sub_obj.get("status")),
                                    )
                                )
                            except Exception as sub_e:
                                logger.warning(f"Skipping malformed subtask {sub_idx}: {sub_e}")
                        
                        story_hours = coerce_int(story_obj.get("estimated_hours"), 0)
                        stories.append(
                            Story(
                                id=story_obj.get("id") or f"story_{epic_idx}_{story_idx}",
                                title=story_obj.get("title") or "Story",
                                description=story_obj.get("description") or "",
                                acceptance_criteria=coerce_list_of_strings(story_obj.get("acceptance_criteria")),
                                priority=coerce_priority(story_obj.get("priority")),
                                estimated_hours=story_hours,
                                status=coerce_status(story_obj.get("status")),
                                subtasks=subtasks,
                            )
                        )
                    except Exception as story_e:
                        logger.warning(f"Skipping malformed story {story_idx}: {story_e}")
                
                epic_hours = coerce_int(epic_obj.get("estimated_hours"), sum(coerce_int(s.estimated_hours, 0) for s in stories))
                total_estimated += epic_hours
                epics.append(
                    Epic(
                        id=epic_obj.get("id") or f"epic_{epic_idx}",
                        title=epic_obj.get("title") or "Epic",
                        description=epic_obj.get("description") or "",
                        priority=coerce_priority(epic_obj.get("priority")),
                        estimated_hours=epic_hours,
                        status=coerce_status(epic_obj.get("status")),
                        stories=stories,
                    )
                )
                logger.info(f"Successfully processed epic {epic_idx}: {epic_obj.get('title', 'Unknown')}")
            except Exception as epic_e:
                logger.warning(f"Skipping malformed epic {epic_idx}: {epic_e}")

        # Do not invent fallback content; honor the LLM output strictly
        if not epics and source_epics:
            logger.warning("Parsed epics list was empty after validation despite non-empty source; keeping empty result.")

        # Fallback totals if missing
        total_estimated = coerce_int(data.get("total_estimated_hours"), total_estimated)
        timeline_weeks = coerce_int(data.get("timeline_weeks"), max(1, (total_estimated + 39) // 40))

        logger.info(f"Final decomposition: {len(epics)} epics, {total_estimated} hours, {timeline_weeks} weeks")

        model = RequirementsDecomposition(
            document_id="",  # set by caller
            created_at=datetime.now(),
            epics=epics,
            total_estimated_hours=total_estimated,
            timeline_weeks=timeline_weeks,
        )

        return model, raw_response  # Return the original raw response
    
    async def suggest_assignees(self, requirements: RequirementsDecomposition, team_members: List[Dict[str, Any]]) -> Dict[str, str]:
        """Suggest assignees for tasks based on team member skills and availability"""
        
        team_info = "\n".join([
            f"- {member['display_name']} ({member.get('email_address', 'No email')})"
            for member in team_members
        ])
        
        tasks_info = []
        for epic in requirements.epics:
            for story in epic.stories:
                tasks_info.append(f"Story: {story.title} - {story.description}")
                for subtask in story.subtasks:
                    tasks_info.append(f"  Subtask: {subtask.title} - {subtask.description}")
        
        prompt = f"""
        Based on the following team members and tasks, suggest appropriate assignees for each task.
        
        Team Members:
        {team_info}
        
        Tasks to Assign:
        {chr(10).join(tasks_info)}
        
        Consider:
        1. Task complexity and required skills
        2. Workload distribution
        3. Team member expertise areas
        4. Task dependencies
        
        Return as JSON mapping task IDs to assignee display names:
        {{
            "task_id": "assignee_name",
            "story_1": "John Doe",
            "subtask_1": "Jane Smith"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert project manager who specializes in task assignment and team management. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            content = response.choices[0].message.content
            cleaned_content = self._clean_and_validate_json(content)
            assignments = json.loads(cleaned_content)
            
            return assignments
            
        except Exception as e:
            logger.error(f"Error suggesting assignees: {str(e)}")
            return {}

    def generate_assignee_suggestions(self, users: List[Dict], tasks: List[Dict]) -> tuple[Dict[str, str], Dict[str, str]]:
        """Generate smart assignee suggestions using AI based on task context and user roles"""
        
        # Initialize variables for fallback
        users_info = []
        tasks_info = []
        
        try:
            # Prepare user information for AI
            for user in users:
                users_info.append({
                    "account_id": getattr(user, "account_id", ""),
                    "display_name": getattr(user, "display_name", ""),
                    "role": getattr(user, "role", ""),
                    "email": getattr(user, "email_address", "")
                })
            
            # Prepare task information for AI
            for task in tasks:
                tasks_info.append({
                    "id": getattr(task, "id", ""),
                    "title": getattr(task, "title", ""),
                    "description": getattr(task, "description", ""),
                    "team": getattr(task, "team", ""),
                    "priority": getattr(task, "priority", ""),
                    "task_type": getattr(task, "task_type", "")
                })
            
            # Log the data being sent to AI for debugging
            logger.info(f"Users info being sent to AI: {json.dumps(users_info, indent=2)}")
            logger.info(f"Tasks info being sent to AI: {json.dumps(tasks_info, indent=2)}")
            
            # Create the prompt for AI
            prompt = f"""
You are a project manager assigning tasks to team members based on their roles and expertise.

Available Team Members:
{json.dumps(users_info, indent=2)}

Tasks to Assign:
{json.dumps(tasks_info, indent=2)}

IMPORTANT: You MUST assign EVERY task to a team member. Do not leave any task unassigned.

Assignment Rules:
1. Match task team field with user role (e.g., "frontend" team → "frontend" role)
2. For epics, assign to users with "product" or "manager" roles
3. For stories/subtasks, match the team field with user role
4. If no exact role match, choose the closest match
5. If multiple people have the same role, distribute evenly
6. If no role is specified for a user, assign based on task context

Return your response as a JSON object with this exact structure:
{{
  "suggestions": {{
    "task_id_1": "user_account_id_1",
    "task_id_2": "user_account_id_2"
  }},
  "reasoning": {{
    "task_id_1": "Brief explanation of why this person was assigned",
    "task_id_2": "Brief explanation of why this person was assigned"
  }}
}}

Example:
If you have a task with team "frontend" and a user with role "frontend", assign that task to that user.
If you have an epic and a user with role "product", assign the epic to that user.

CRITICAL: Every task must have an assignment. Do not return empty suggestions.
"""

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert project manager who assigns tasks to team members based on their roles and expertise. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=8000
            )
            
            # Parse the response
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"AI Response for assignee suggestions: {ai_response}")
            
            # Try to parse the JSON response
            try:
                # Clean the response to handle truncated JSON
                cleaned_response = ai_response
                
                # If the response is truncated, try to fix it
                if not cleaned_response.endswith('}'):
                    # Try to find the last complete key-value pair
                    # Look for the pattern: "key": "value"
                    last_complete = cleaned_response.rfind('": "')
                    if last_complete != -1:
                        # Find the end of the value (next quote)
                        end_quote = cleaned_response.find('"', last_complete + 4)
                        if end_quote != -1:
                            # Truncate at the end of the last complete entry
                            cleaned_response = cleaned_response[:end_quote + 1] + '}'
                        else:
                            # If we can't find the end quote, try to find the last complete entry
                            # Look for the last complete key
                            last_key = cleaned_response.rfind('"')
                            if last_key != -1:
                                # Find the start of the key
                                key_start = cleaned_response.rfind('"', 0, last_key - 1)
                                if key_start != -1:
                                    # Truncate before the incomplete key
                                    cleaned_response = cleaned_response[:key_start] + '}'
                                else:
                                    cleaned_response = cleaned_response + '}'
                            else:
                                cleaned_response = cleaned_response + '}'
                    else:
                        # If we can't find any complete entries, just close the JSON
                        cleaned_response = cleaned_response + '}'
                
                result = json.loads(cleaned_response)
                suggestions = result.get("suggestions", {})
                reasoning = result.get("reasoning", {})
                
                # Validate that all task IDs have suggestions
                for task in tasks_info:
                    task_id = task["id"]
                    if task_id not in suggestions:
                        # Fallback: assign to first available user
                        if users_info:
                            suggestions[task_id] = users_info[0]["account_id"]
                            reasoning[task_id] = "Fallback assignment - no specific role match found"
                
                # If still no suggestions, use fallback logic
                if not suggestions and tasks_info and users_info:
                    logger.warning("AI returned empty suggestions, using fallback logic")
                    return self._fallback_assignments(users_info, tasks_info)
                
                return suggestions, reasoning
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                # Fallback: simple role-based assignment
                return self._fallback_assignments(users_info, tasks_info)
                
        except Exception as e:
            logger.error(f"Error generating assignee suggestions: {str(e)}")
            # Fallback: simple role-based assignment
            return self._fallback_assignments(users_info, tasks_info)
    
    def _fallback_assignments(self, users_info: List[Dict], tasks_info: List[Dict]) -> tuple[Dict[str, str], Dict[str, str]]:
        """Fallback assignment logic when AI fails"""
        suggestions = {}
        reasoning = {}
        
        # Create role mapping
        role_to_users = {}
        for user in users_info:
            role = user.get("role", "").lower()
            if role not in role_to_users:
                role_to_users[role] = []
            role_to_users[role].append(user["account_id"])
        
        # Assign tasks based on team field
        for task in tasks_info:
            task_id = task["id"]
            team = task.get("team", "").lower()
            task_type = task.get("task_type", "")
            
            # Determine appropriate role
            if task_type == "epic":
                target_role = "product"
            elif team in ["frontend", "ui", "ux"]:
                target_role = "frontend"
            elif team in ["backend", "api", "server"]:
                target_role = "backend"
            elif team in ["qa", "testing", "test"]:
                target_role = "qa"
            elif team in ["devops", "infrastructure", "deployment"]:
                target_role = "devops"
            elif team in ["data", "analytics", "database"]:
                target_role = "data"
            else:
                target_role = "backend"  # Default fallback
            
            # Find user with matching role
            if target_role in role_to_users and role_to_users[target_role]:
                user_id = role_to_users[target_role][0]  # Take first user with this role
                suggestions[task_id] = user_id
                reasoning[task_id] = f"Assigned to {target_role} role based on task team '{team}'"
            elif users_info:
                # Fallback to first available user
                suggestions[task_id] = users_info[0]["account_id"]
                reasoning[task_id] = f"No {target_role} role found, assigned to first available user"
        
        return suggestions, reasoning