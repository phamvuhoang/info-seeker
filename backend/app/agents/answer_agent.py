from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from typing import Dict, Any, List
import asyncio
from datetime import datetime
from ..core.config import settings
from ..services.sse_manager import progress_manager
from .base_streaming_agent import BaseStreamingAgent


class AnswerAgent(BaseStreamingAgent):
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
                    prefix="infoseeker_answer",
                    host=host,
                    port=port,
                    db=db
                )
            except Exception as e:
                print(f"Warning: Failed to configure Redis storage: {e}")
                storage = None

        super().__init__(
            name="Answer Generator",
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            description="Final answer generation specialist",
            instructions=[
                "You are the final answer generation specialist for InfoSeeker.",
                "Create clear, concise, and well-structured responses.",
                "Ensure proper citation and source attribution.",
                "Adapt tone and detail level to user needs.",
                "Provide actionable insights when appropriate.",
                "Structure answers with clear headings and sections.",
                "Include confidence indicators where relevant.",
                "Highlight key findings and important information.",
                "Provide balanced perspectives when multiple viewpoints exist.",
                "End with a clear summary or conclusion.",
                "IMPORTANT: Always respond in the same language as the user's query.",
                "If you receive a language instruction at the beginning of the message, follow it strictly.",
                "Maintain the same language throughout your entire response."
            ],
            storage=storage,
            show_tool_calls=True,
            markdown=True
        )
        
        self.session_id = session_id
    
    async def generate_final_answer(self, 
                                  query: str,
                                  synthesis: str = "",
                                  validation: Dict[str, Any] = None,
                                  sources: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate the final comprehensive answer"""
        
        try:
            # Broadcast progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "started",
                        "message": "Generating final comprehensive answer..."
                    }
                )
            
            # Prepare answer context
            answer_context = self._prepare_answer_context(query, synthesis, validation, sources)
            
            # Create answer prompt
            answer_prompt = f"""
Please generate a comprehensive, well-structured answer to the following query:

Query: {query}

{answer_context}

Instructions for the final answer:
1. Create a clear, engaging response that directly addresses the query
2. Structure the answer with appropriate headings and sections
3. Include proper source citations throughout
4. Provide balanced information from multiple perspectives if applicable
5. Highlight key findings and important insights
6. Include confidence indicators where relevant
7. End with a clear summary or conclusion
8. Make the answer actionable and useful for the user
9. Use markdown formatting for better readability
10. Ensure the tone is professional yet accessible

Please generate the final answer now.
"""
            
            # Run answer generation
            response = await super().arun(answer_prompt)
            
            # Analyze the generated answer
            answer_analysis = self._analyze_answer(response.content, sources, validation)
            
            # Broadcast progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "completed",
                        "message": f"Final answer generated. Quality score: {answer_analysis['quality_score']:.2f}",
                        "result_preview": response.content[:200] + "..." if len(response.content) > 200 else response.content
                    }
                )
            
            return {
                "status": "success",
                "answer": response.content,
                "analysis": answer_analysis,
                "query": query,
                "sources_used": len(sources) if sources else 0
            }
            
        except Exception as e:
            error_msg = f"Error generating final answer: {str(e)}"
            
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
                "answer": "",
                "query": query
            }
    
    def _prepare_answer_context(self, 
                              query: str,
                              synthesis: str = "",
                              validation: Dict[str, Any] = None,
                              sources: List[Dict[str, Any]] = None) -> str:
        """Prepare context for answer generation"""
        
        context = ""
        
        # Add synthesis
        if synthesis:
            context += f"## Synthesized Information:\n{synthesis}\n\n"
        
        # Add validation results
        if validation and validation.get("status") == "success":
            validation_analysis = validation.get("analysis", {})
            context += "## Validation Results:\n"
            context += f"- Confidence Score: {validation_analysis.get('confidence_score', 0.7):.2f}\n"
            context += f"- Status: {validation_analysis.get('status', 'unknown')}\n"
            context += f"- Source Reliability: {validation_analysis.get('source_reliability', 'unknown')}\n"
            
            if validation_analysis.get("issues_found"):
                context += f"- Issues Found: {', '.join(validation_analysis['issues_found'])}\n"
            
            context += "\n"
        
        # Add source summary
        if sources:
            context += "## Available Sources:\n"
            rag_sources = [s for s in sources if s.get('source_type') != 'web_search']
            web_sources = [s for s in sources if s.get('source_type') == 'web_search']
            
            if rag_sources:
                context += f"- Knowledge Base Sources: {len(rag_sources)}\n"
            if web_sources:
                context += f"- Web Search Sources: {len(web_sources)}\n"
            
            context += "\n### Source Details:\n"
            for i, source in enumerate(sources[:10], 1):  # Limit to top 10 sources
                context += f"{i}. **{source.get('title', 'Untitled')}**\n"
                if source.get('url'):
                    context += f"   - URL: {source['url']}\n"
                if source.get('similarity_score'):
                    context += f"   - Similarity: {source['similarity_score']:.2f}\n"
                if source.get('relevance_score'):
                    context += f"   - Relevance: {source['relevance_score']:.2f}\n"
                context += f"   - Type: {source.get('source_type', 'unknown')}\n\n"
        
        return context
    
    def _analyze_answer(self,
                       answer: str,
                       sources: List[Dict[str, Any]] = None,
                       validation: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze the generated answer for quality metrics"""

        analysis = {
            "quality_score": 0.5,  # Start with base score
            "word_count": len(answer.split()),
            "has_citations": False,
            "has_structure": False,
            "confidence_level": "medium",
            "completeness": "adequate"
        }

        # Check for citations
        citation_indicators = ["source:", "according to", "based on", "reference:", "[", "]", "http", "www.", ".com", ".org"]
        analysis["has_citations"] = any(indicator in answer.lower() for indicator in citation_indicators)

        # Check for structure
        structure_indicators = ["#", "##", "###", "**", "*", "1.", "2.", "3.", "•", "-"]
        analysis["has_structure"] = any(indicator in answer for indicator in structure_indicators)

        # Calculate quality score based on multiple factors
        quality_score = 0.3  # Base score

        # Content quality factors
        if analysis["has_citations"]:
            quality_score += 0.25  # Strong boost for citations
        if analysis["has_structure"]:
            quality_score += 0.15  # Good boost for structure
        if analysis["word_count"] > 100:
            quality_score += 0.1   # Boost for comprehensive answers
        if analysis["word_count"] > 300:
            quality_score += 0.05  # Additional boost for detailed answers

        # Source quality factors
        if sources:
            source_count = len(sources)
            if source_count >= 3:
                quality_score += 0.1
            if source_count >= 5:
                quality_score += 0.05

            # Check source diversity
            unique_domains = set()
            for source in sources:
                url = source.get('url', '')
                if url:
                    try:
                        from urllib.parse import urlparse
                        domain = urlparse(url).netloc
                        unique_domains.add(domain)
                    except:
                        pass

            if len(unique_domains) >= 3:
                quality_score += 0.1  # Boost for diverse sources

        # Content analysis
        answer_lower = answer.lower()

        # Check for comprehensive coverage
        comprehensive_indicators = ["overview", "summary", "conclusion", "key points", "important", "significant"]
        if any(indicator in answer_lower for indicator in comprehensive_indicators):
            quality_score += 0.05

        # Check for balanced perspective
        balance_indicators = ["however", "although", "on the other hand", "alternatively", "different", "various"]
        if any(indicator in answer_lower for indicator in balance_indicators):
            quality_score += 0.05

        # Factor in validation confidence if available
        if validation and validation.get("analysis", {}).get("confidence_score"):
            validation_confidence = validation["analysis"]["confidence_score"]
            # Weight validation confidence heavily in quality calculation
            quality_score = (quality_score * 0.6) + (validation_confidence * 0.4)

        # Ensure quality score is within reasonable bounds
        analysis["quality_score"] = min(max(quality_score, 0.1), 0.95)
        
        # Determine confidence level
        if analysis["quality_score"] > 0.8:
            analysis["confidence_level"] = "high"
        elif analysis["quality_score"] > 0.6:
            analysis["confidence_level"] = "medium"
        else:
            analysis["confidence_level"] = "low"
        
        # Assess completeness
        if analysis["word_count"] > 300 and analysis["has_citations"] and analysis["has_structure"]:
            analysis["completeness"] = "comprehensive"
        elif analysis["word_count"] > 150:
            analysis["completeness"] = "adequate"
        else:
            analysis["completeness"] = "basic"
        
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
                        "message": "Answer Generator is creating final response..."
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
                        "message": "Final answer generation completed.",
                        "result_preview": response.content[:200] + "..." if len(response.content) > 200 else response.content
                    }
                )
            
            return response
            
        except Exception as e:
            error_msg = f"Answer Agent error: {str(e)}"
            
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


def create_answer_agent(session_id: str = None) -> AnswerAgent:
    """Create an answer agent with optional session tracking"""
    return AnswerAgent(session_id=session_id)
