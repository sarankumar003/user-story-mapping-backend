"""
Streaming AI Agent Service
Handles AI-powered document processing with streaming responses and validation
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, AsyncGenerator, Union
import re
import uuid
from openai import OpenAI, AsyncOpenAI
from app.core.config import settings
from app.models.document import DocumentSummary
from app.models.requirement import Epic, Story, Subtask, RequirementsDecomposition, TaskStatus, Priority

logger = logging.getLogger(__name__)


class StreamingAIAgent:
    """
    Enhanced AI Agent with streaming support and validation
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.max_tokens = 16000  # Increased from 8000
        self.chunk_size = 4000   # Process in chunks to avoid truncation
        
    async def generate_summary_streaming(self, document_text: str) -> AsyncGenerator[str, None]:
        """Generate BRD summary using streaming AI"""
        
        prompt = f"""
        Analyze this Business Requirements Document and provide a comprehensive summary.
        
        Document Text:
        {document_text[:8000]}  # Limit input size
        
        Provide a structured summary with:
        1. Project Overview
        2. Key Requirements
        3. Business Objectives
        4. Technical Requirements
        5. Assumptions and Constraints
        6. Risks and Dependencies
        
        Format as JSON with keys: overview, requirements, objectives, technical_requirements, assumptions, risks.
        """
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert business analyst. Provide clear, structured summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=self.max_tokens,
                stream=True,
                response_format={"type": "json_object"}
            )
            
            full_response = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content
                    
            # Validate the complete response
            if not self._validate_json_response(full_response):
                logger.warning("Summary response validation failed, attempting repair")
                repaired = self._repair_json_response(full_response)
                if repaired:
                    yield repaired
                    
        except Exception as e:
            logger.error(f"Error in streaming summary generation: {e}")
            yield json.dumps({"error": str(e)})
    
    async def decompose_requirements_streaming(self, summary: DocumentSummary) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate requirements decomposition with streaming and chunking"""
        
        # First, determine if we need chunking based on summary complexity
        summary_complexity = self._assess_summary_complexity(summary)
        
        if summary_complexity > 0.7:  # High complexity - use chunking
            logger.info("High complexity detected, using chunked decomposition")
            async for chunk_result in self._chunked_decomposition(summary):
                yield chunk_result
        else:
            logger.info("Standard complexity, using single decomposition")
            async for result in self._single_decomposition(summary):
                yield result
    
    def _assess_summary_complexity(self, summary: DocumentSummary) -> float:
        """Assess the complexity of the summary to determine if chunking is needed"""
        complexity_score = 0.0
        
        # Factor 1: Number of key features
        req_count = len(summary.key_features or [])
        if req_count > 20:
            complexity_score += 0.3
        elif req_count > 10:
            complexity_score += 0.2
        
        # Factor 2: Length of technical requirements
        tech_req_length = len(str(summary.technical_requirements or ""))
        if tech_req_length > 2000:
            complexity_score += 0.3
        elif tech_req_length > 1000:
            complexity_score += 0.2
        
        # Factor 3: Number of risks and dependencies
        risk_count = len(summary.risks or [])
        if risk_count > 5:
            complexity_score += 0.2
        
        # Factor 4: Overall text length
        total_length = len(str(summary))
        if total_length > 5000:
            complexity_score += 0.2
        
        return min(complexity_score, 1.0)
    
    async def _single_decomposition(self, summary: DocumentSummary) -> AsyncGenerator[Dict[str, Any], None]:
        """Single decomposition for standard complexity"""
        
        system_prompt = """
        You are an expert product manager and technical architect. 
        Decompose business requirements into epics, stories, and subtasks.
        Always return valid JSON. If you reach token limits, ensure the JSON is properly closed.
        """
        
        prompt = f"""
        Based on this BRD summary, create a comprehensive decomposition:
        
        Project Name: {summary.project_name}
        Project Description: {summary.project_description}
        Objectives: {summary.objectives}
        Scope: {summary.scope}
        Key Features: {summary.key_features}
        Technical Requirements: {summary.technical_requirements}
        Assumptions: {summary.assumptions}
        Risks: {summary.risks}
        
        Return exactly one JSON object with keys: epics (array), total_estimated_hours (number), timeline_weeks (number).
        
        Each epic must include:
        - id: unique identifier (EPIC-1, EPIC-2, etc.)
        - title: descriptive epic name
        - description: comprehensive description including business justification
        - priority: Low, Medium, High, or Critical
        - estimated_hours: total hours for the epic
        - status: "To Do"
        - stories: array of user stories
        
        Each story must include:
        - id: unique identifier (FE-1, BE-1, etc.)
        - title: user story title
        - description: detailed description
        - acceptance_criteria: array of specific, testable criteria
        - priority: Low, Medium, High, or Critical
        - estimated_hours: story point estimation
        - status: "To Do"
        - subtasks: array of technical subtasks
        
        Each subtask must include:
        - id: unique identifier (FE-1-1, BE-1-1, etc.)
        - title: specific task title
        - description: detailed technical description
        - priority: Low, Medium, High, or Critical
        - estimated_hours: specific time estimate
        - status: "To Do"
        
        IMPORTANT: If you approach token limits, ensure the JSON is properly closed with all necessary braces.
        Consider all teams: Frontend, Backend, Data Engineers, DevOps, IT, HR, Legal, QA, UX/UI, Product Management.
        """
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=self.max_tokens,
                stream=True,
                response_format={"type": "json_object"}
            )
            
            full_response = ""
            chunk_count = 0
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    chunk_count += 1
                    
                    # Yield progress updates every 10 chunks
                    if chunk_count % 10 == 0:
                        yield {
                            "type": "progress",
                            "chunks_received": chunk_count,
                            "response_length": len(full_response)
                        }
            
            # Validate and yield final result
            validation_result = self._validate_and_repair_response(full_response)
            yield {
                "type": "complete",
                "data": validation_result["data"],
                "warnings": validation_result["warnings"],
                "was_repaired": validation_result["was_repaired"]
            }
            
        except Exception as e:
            logger.error(f"Error in single decomposition: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def _chunked_decomposition(self, summary: DocumentSummary) -> AsyncGenerator[Dict[str, Any], None]:
        """Chunked decomposition for high complexity summaries"""
        
        # Split requirements into chunks
        requirements_chunks = self._split_requirements_into_chunks(summary)
        
        all_epics = []
        total_hours = 0
        chunk_index = 0
        
        for chunk in requirements_chunks:
            chunk_index += 1
            yield {
                "type": "chunk_start",
                "chunk_index": chunk_index,
                "total_chunks": len(requirements_chunks)
            }
            
            # Process each chunk
            async for result in self._process_requirement_chunk(chunk, chunk_index):
                if result["type"] == "complete":
                    all_epics.extend(result["data"].get("epics", []))
                    total_hours += result["data"].get("total_estimated_hours", 0)
                    yield {
                        "type": "chunk_complete",
                        "chunk_index": chunk_index,
                        "epics_count": len(result["data"].get("epics", []))
                    }
                elif result["type"] == "error":
                    yield result
        
        # Combine all results
        final_result = {
            "epics": all_epics,
            "total_estimated_hours": total_hours,
            "timeline_weeks": max(1, total_hours // 40)  # Assume 40 hours per week
        }
        
        yield {
            "type": "complete",
            "data": final_result,
            "warnings": [],
            "was_repaired": False
        }
    
    def _split_requirements_into_chunks(self, summary: DocumentSummary) -> List[Dict[str, Any]]:
        """Split requirements into manageable chunks"""
        chunks = []
        
        # Get all key features
        all_features = summary.key_features or []
        tech_requirements = summary.technical_requirements or ""
        
        # Split into chunks of manageable size
        chunk_size = 5  # 5 features per chunk
        for i in range(0, len(all_features), chunk_size):
            chunk_features = all_features[i:i + chunk_size]
            
            chunk = {
                "project_name": summary.project_name,
                "project_description": summary.project_description,
                "objectives": summary.objectives if i == 0 else [],
                "scope": summary.scope if i == 0 else [],
                "key_features": chunk_features,
                "technical_requirements": tech_requirements if i == 0 else "",  # Include tech reqs only in first chunk
                "assumptions": summary.assumptions if i == 0 else [],
                "risks": summary.risks if i == 0 else [],
                "chunk_index": i // chunk_size + 1
            }
            chunks.append(chunk)
        
        return chunks
    
    async def _process_requirement_chunk(self, chunk: Dict[str, Any], chunk_index: int) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a single requirement chunk"""
        
        prompt = f"""
        Process this chunk of requirements (Chunk {chunk_index}):
        
        Project Name: {chunk['project_name']}
        Project Description: {chunk['project_description']}
        Objectives: {chunk['objectives']}
        Scope: {chunk['scope']}
        Key Features: {chunk['key_features']}
        Technical Requirements: {chunk['technical_requirements']}
        Assumptions: {chunk['assumptions']}
        Risks: {chunk['risks']}
        
        Create epics, stories, and subtasks for this chunk.
        Use chunk-specific IDs: EPIC-{chunk_index}-1, EPIC-{chunk_index}-2, etc.
        
        Return JSON with keys: epics (array), total_estimated_hours (number).
        """
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert product manager. Create detailed epics and stories."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=self.max_tokens,
                stream=True,
                response_format={"type": "json_object"}
            )
            
            full_response = ""
            async for chunk_data in stream:
                if chunk_data.choices[0].delta.content:
                    full_response += chunk_data.choices[0].delta.content
            
            # Validate and return result
            validation_result = self._validate_and_repair_response(full_response)
            yield {
                "type": "complete",
                "data": validation_result["data"],
                "warnings": validation_result["warnings"],
                "was_repaired": validation_result["was_repaired"]
            }
            
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_index}: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    def _validate_json_response(self, response: str) -> bool:
        """Validate if the response is valid JSON"""
        try:
            json.loads(response)
            return True
        except json.JSONDecodeError:
            return False
    
    def _repair_json_response(self, response: str) -> Optional[str]:
        """Attempt to repair a malformed JSON response"""
        try:
            # Remove any trailing incomplete content
            response = response.strip()
            
            # Find the last complete JSON structure
            brace_count = 0
            last_valid_pos = -1
            
            for i, char in enumerate(response):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_valid_pos = i
            
            if last_valid_pos > 0:
                repaired = response[:last_valid_pos + 1]
                if self._validate_json_response(repaired):
                    return repaired
            
            # If that doesn't work, try to close open structures
            if response.count('{') > response.count('}'):
                missing_braces = response.count('{') - response.count('}')
                repaired = response + '}' * missing_braces
                if self._validate_json_response(repaired):
                    return repaired
            
            return None
            
        except Exception as e:
            logger.error(f"Error repairing JSON response: {e}")
            return None
    
    def _validate_and_repair_response(self, response: str) -> Dict[str, Any]:
        """Validate response and attempt repair if needed"""
        warnings = []
        was_repaired = False
        
        # First, try direct parsing
        try:
            data = json.loads(response)
            return {
                "data": data,
                "warnings": warnings,
                "was_repaired": was_repaired
            }
        except json.JSONDecodeError as e:
            logger.warning(f"JSON validation failed: {e}")
            warnings.append(f"JSON validation failed: {str(e)}")
            
            # Attempt repair
            repaired = self._repair_json_response(response)
            if repaired:
                try:
                    data = json.loads(repaired)
                    was_repaired = True
                    warnings.append("Response was repaired due to truncation")
                    return {
                        "data": data,
                        "warnings": warnings,
                        "was_repaired": was_repaired
                    }
                except json.JSONDecodeError:
                    pass
            
            # If repair failed, return empty structure
            warnings.append("Could not repair response, returning empty structure")
            return {
                "data": {"epics": [], "total_estimated_hours": 0, "timeline_weeks": 0},
                "warnings": warnings,
                "was_repaired": was_repaired
            }
    
    def _clean_and_validate_json(self, raw_response: str) -> str:
        """Clean and validate JSON response (legacy method for compatibility)"""
        # Remove any markdown code fences
        cleaned = re.sub(r'^```json\s*', '', raw_response, flags=re.MULTILINE)
        cleaned = re.sub(r'\s*```$', '', cleaned, flags=re.MULTILINE)
        
        # Remove any leading/trailing whitespace
        cleaned = cleaned.strip()
        
        return cleaned


# Utility functions for compatibility
def coerce_priority(priority: Any) -> Priority:
    """Coerce priority to Priority enum"""
    if isinstance(priority, Priority):
        return priority
    
    priority_str = str(priority).lower() if priority else "medium"
    if priority_str in ["critical", "high", "medium", "low"]:
        return Priority(priority_str.title())
    
    return Priority.Medium


def coerce_status(status: Any) -> TaskStatus:
    """Coerce status to TaskStatus enum"""
    if isinstance(status, TaskStatus):
        return status
    
    status_str = str(status).lower() if status else "to_do"
    if status_str in ["to_do", "in_progress", "done", "blocked"]:
        return TaskStatus(status_str.title())
    
    return TaskStatus.To_Do


def coerce_int(value: Any, default: int = 0) -> int:
    """Coerce value to integer"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def coerce_list_of_strings(value: Any) -> List[str]:
    """Coerce value to list of strings"""
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    elif value is not None:
        return [str(value)]
    else:
        return []
