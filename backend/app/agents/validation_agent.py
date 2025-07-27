from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from typing import Dict, Any, List
import asyncio
from datetime import datetime
from ..core.config import settings
from ..services.sse_manager import progress_manager
from .base_streaming_agent import BaseStreamingAgent


class ValidationAgent(BaseStreamingAgent):
    def __init__(self, session_id: str = None):
        # Configure storage if session_id provided
        storage = None
        if session_id:
            try:
                # Parse Redis URL more safely
                redis_parts = settings.redis_url.replace("redis://", "").split("/")
                host_port = redis_parts[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 6379
                db = int(redis_parts[1]) if len(redis_parts) > 1 else 0

                storage = RedisStorage(
                    prefix="infoseeker_validation",
                    host=host,
                    port=port,
                    db=db
                )
            except Exception as e:
                print(f"Warning: Failed to configure Redis storage: {e}")
                storage = None

        super().__init__(
            name="Information Validator",
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            description="Information validation specialist",
            instructions=[
                "You are the information validation specialist for InfoSeeker.",
                "Verify accuracy and consistency of synthesized information.",
                "Check for potential biases or misinformation indicators.",
                "Assess source credibility and reliability.",
                "Flag any inconsistencies or concerns in the information.",
                "Evaluate the logical coherence of the synthesized response.",
                "Check for factual accuracy where possible.",
                "Identify areas where claims need additional verification.",
                "Provide confidence scores for different aspects of the information.",
                "Suggest improvements or corrections if needed."
            ],
            storage=storage,
            show_tool_calls=True,
            markdown=True
        )
        
        self.session_id = session_id
    
    async def validate_information(self, 
                                 synthesis: str,
                                 sources: List[Dict[str, Any]] = None,
                                 query: str = "") -> Dict[str, Any]:
        """Validate synthesized information"""
        
        try:
            # Broadcast progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "started",
                        "message": "Validating information accuracy and consistency..."
                    }
                )
            
            # Prepare validation context
            validation_context = self._prepare_validation_context(synthesis, sources, query)
            
            # Create validation prompt
            validation_prompt = f"""
Please validate the following synthesized information:

Query: {query}

Synthesized Response:
{synthesis}

{validation_context}

Please provide a validation report that includes:
1. Accuracy Assessment: Check for factual correctness
2. Consistency Check: Identify any contradictions
3. Source Reliability: Evaluate the credibility of sources
4. Bias Detection: Look for potential biases or one-sided perspectives
5. Completeness: Assess if important information is missing
6. Confidence Score: Rate overall confidence (0-1) in the information
7. Recommendations: Suggest any improvements or corrections

Format your response as a structured validation report.
"""
            
            # Run validation
            response = await super().arun(validation_prompt)
            
            # Extract confidence score and issues
            validation_analysis = self._analyze_validation(response.content, sources)
            
            # Broadcast progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "completed",
                        "message": f"Validation completed. Confidence: {validation_analysis['confidence_score']:.2f}",
                        "result_preview": f"Validation status: {validation_analysis['status']}"
                    }
                )
            
            return {
                "status": "success",
                "validation_report": response.content,
                "analysis": validation_analysis,
                "query": query
            }
            
        except Exception as e:
            error_msg = f"Error validating information: {str(e)}"
            
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "failed",
                        "message": error_msg
                    }
                )
            
            return {
                "status": "error",
                "message": error_msg,
                "validation_report": "",
                "query": query
            }
    
    def _prepare_validation_context(self, 
                                  synthesis: str,
                                  sources: List[Dict[str, Any]] = None,
                                  query: str = "") -> str:
        """Prepare context for validation"""
        
        context = ""
        
        if sources:
            context += "## Source Information for Validation:\n\n"
            for i, source in enumerate(sources, 1):
                context += f"### Source {i}\n"
                context += f"**Type:** {source.get('source_type', 'unknown')}\n"
                context += f"**Title:** {source.get('title', 'Untitled')}\n"
                if source.get('url'):
                    context += f"**URL:** {source['url']}\n"
                if source.get('similarity_score'):
                    context += f"**Similarity Score:** {source['similarity_score']:.2f}\n"
                if source.get('relevance_score'):
                    context += f"**Relevance Score:** {source['relevance_score']:.2f}\n"
                if source.get('timestamp'):
                    context += f"**Timestamp:** {source['timestamp']}\n"
                context += "\n"
        
        context += """
## Validation Criteria:
- Check for factual accuracy
- Identify contradictions between sources
- Assess source credibility
- Look for potential biases
- Evaluate completeness of information
- Rate overall confidence in the response
"""
        
        return context
    
    def _analyze_validation(self, validation_report: str, sources: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze validation report for key metrics"""
        
        analysis = {
            "confidence_score": 0.7,  # Default confidence
            "status": "validated",
            "issues_found": [],
            "source_reliability": "medium",
            "bias_detected": False,
            "completeness": "adequate"
        }
        
        # Simple keyword-based analysis (in production, use more sophisticated NLP)
        report_lower = validation_report.lower()
        
        # Extract confidence score
        if "confidence" in report_lower:
            # Look for patterns like "confidence: 0.8" or "confidence score: 85%"
            import re
            confidence_patterns = [
                r"confidence[:\s]+([0-9]*\.?[0-9]+)",
                r"confidence score[:\s]+([0-9]+)%",
                r"overall confidence[:\s]+([0-9]*\.?[0-9]+)"
            ]
            
            for pattern in confidence_patterns:
                match = re.search(pattern, report_lower)
                if match:
                    score = float(match.group(1))
                    if score > 1:  # Percentage format
                        score = score / 100
                    analysis["confidence_score"] = min(max(score, 0), 1)
                    break
        
        # Check for issues
        issue_keywords = ["contradiction", "inconsistent", "unreliable", "bias", "missing", "incomplete"]
        for keyword in issue_keywords:
            if keyword in report_lower:
                analysis["issues_found"].append(keyword)
        
        # Determine status
        if analysis["confidence_score"] < 0.5:
            analysis["status"] = "low_confidence"
        elif analysis["issues_found"]:
            analysis["status"] = "validated_with_concerns"
        else:
            analysis["status"] = "validated"
        
        # Assess source reliability
        if sources:
            reliable_sources = 0
            total_sources = len(sources)
            
            for source in sources:
                url = source.get('url', '').lower()
                # Simple domain-based reliability check
                reliable_domains = ['wikipedia.org', 'arxiv.org', 'nature.com', 'sciencedirect.com', 'pubmed.ncbi.nlm.nih.gov']
                if any(domain in url for domain in reliable_domains):
                    reliable_sources += 1
            
            reliability_ratio = reliable_sources / total_sources if total_sources > 0 else 0
            if reliability_ratio > 0.7:
                analysis["source_reliability"] = "high"
            elif reliability_ratio > 0.4:
                analysis["source_reliability"] = "medium"
            else:
                analysis["source_reliability"] = "low"
        
        return analysis
    
    async def arun(self, message: str, **kwargs) -> Any:
        """Override arun to add progress tracking"""
        try:
            # Send start notification
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "started",
                        "message": "Information Validator is checking accuracy..."
                    }
                )
            
            # Run the agent with streaming
            response = await self.arun_with_streaming(message, **kwargs)
            
            # Send completion notification
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "completed",
                        "message": "Information validation completed.",
                        "result_preview": response.content[:200] + "..." if len(response.content) > 200 else response.content
                    }
                )
            
            return response
            
        except Exception as e:
            error_msg = f"Validation Agent error: {str(e)}"
            
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "failed",
                        "message": error_msg
                    }
                )
            
            raise e


def create_validation_agent(session_id: str = None) -> ValidationAgent:
    """Create a validation agent with optional session tracking"""
    return ValidationAgent(session_id=session_id)
