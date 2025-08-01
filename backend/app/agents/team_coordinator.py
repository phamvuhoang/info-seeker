from agno.team import Team
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from agno.tools.reasoning import ReasoningTools
from typing import Dict, Any, List
import asyncio
import time
from datetime import datetime
from ..core.config import settings
from ..services.sse_manager import progress_manager
from ..services.document_processor import document_processor  # For search result processing only
from ..services.database_service import database_service
from ..services.vector_embedding_service import vector_embedding_service
from ..utils.performance_monitor import performance_monitor
from ..utils.language_detector import language_detector
from .rag_agent import create_rag_agent
from .web_search_agent import create_web_search_agent
from .synthesis_agent import create_synthesis_agent
from .validation_agent import create_validation_agent
from .answer_agent import create_answer_agent
import logging

logger = logging.getLogger(__name__)


class MultiAgentSearchTeam:
    def __init__(self, session_id: str = None):
        self.session_id = session_id
        self.progress_manager = progress_manager
        self.start_time = None
        self.detected_language = 'en'  # Default to English
        self.language_instruction = ""

        # Shared Redis storage for better performance
        self.shared_storage = self._create_shared_storage()

        # Create specialized agents with shared storage
        self.rag_agent = create_rag_agent(session_id)
        self.web_agent = create_web_search_agent(session_id)
        self.synthesis_agent = create_synthesis_agent(session_id)
        self.validation_agent = create_validation_agent(session_id)
        self.answer_agent = create_answer_agent(session_id)

        # Create orchestrator agent
        self.orchestrator = self._create_orchestrator()

        # Create the team
        self.team = self._create_team()

    def _create_shared_storage(self):
        """Create shared Redis storage for all agents"""
        if not self.session_id:
            return None

        try:
            # Parse Redis URL more safely
            redis_parts = settings.redis_url.replace("redis://", "").split("/")
            host_port = redis_parts[0].split(":")
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 6379
            db = int(redis_parts[1]) if len(redis_parts) > 1 else 0

            return RedisStorage(
                prefix="infoseeker_shared",
                host=host,
                port=port,
                db=db
            )
        except Exception as e:
            print(f"Warning: Failed to configure shared Redis storage: {e}")
            return None

    def _create_orchestrator(self) -> Agent:
        """Create the orchestrator agent"""
        # Configure storage if session_id provided
        storage = None
        if self.session_id:
            try:
                # Parse Redis URL more safely
                redis_parts = settings.redis_url.replace("redis://", "").split("/")
                host_port = redis_parts[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 6379
                db = int(redis_parts[1]) if len(redis_parts) > 1 else 0

                storage = RedisStorage(
                    prefix="infoseeker_orchestrator",
                    host=host,
                    port=port,
                    db=db
                )
            except Exception as e:
                print(f"Warning: Failed to configure Redis storage: {e}")
                storage = None

        return Agent(
            name="Search Orchestrator",
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            tools=[ReasoningTools(add_instructions=True)],
            description="Search orchestrator for InfoSeeker multi-agent system",
            instructions=[
                "You are the search orchestrator for InfoSeeker.",
                "Coordinate multiple agents to provide comprehensive answers.",
                "Analyze queries and delegate to appropriate specialist agents.",
                "Ensure all agents work together efficiently.",
                "Provide real-time progress updates to users.",
                "Make decisions about which agents to use based on the query type.",
                "Combine results from multiple agents into coherent responses."
            ],
            storage=storage,
            show_tool_calls=True,
            markdown=True
        )
    
    def _create_team(self) -> Team:
        """Create the multi-agent team"""
        # Configure storage if session_id provided
        storage = None
        if self.session_id:
            try:
                # Parse Redis URL more safely
                redis_parts = settings.redis_url.replace("redis://", "").split("/")
                host_port = redis_parts[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 6379
                db = int(redis_parts[1]) if len(redis_parts) > 1 else 0

                storage = RedisStorage(
                    prefix="infoseeker_team",
                    host=host,
                    port=port,
                    db=db
                )
            except Exception as e:
                print(f"Warning: Failed to configure Redis storage: {e}")
                storage = None

        return Team(
            name="InfoSeeker Search Team",
            mode="coordinate",  # Agents work together in sequence
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            members=[
                self.rag_agent,
                self.web_agent,
                self.synthesis_agent,
                self.validation_agent,
                self.answer_agent
            ],
            instructions=[
                "First, search the knowledge base for relevant stored information using the RAG Specialist.",
                "Then, search the web for current information using the Web Search Specialist.",
                "Next, synthesize information from both sources using the Information Synthesizer.",
                "Then, validate the synthesized information using the Information Validator.",
                "Finally, generate a comprehensive answer using the Answer Generator.",
                "Each agent should complete their task before the next agent begins.",
                "Provide source attribution and maintain accuracy throughout."
            ],
            storage=storage,
            show_tool_calls=True,
            show_members_responses=True,
            markdown=True
        )
    
    async def execute_hybrid_search(self,
                                  query: str,
                                  include_rag: bool = True,
                                  include_web: bool = True,
                                  max_results: int = 10) -> Dict[str, Any]:
        """Execute the multi-agent hybrid search workflow with optimized performance"""

        async with performance_monitor.measure_operation("hybrid_search", self.session_id):
            self.start_time = time.time()

            try:
                # Save agent workflow session start
                await database_service.save_agent_workflow_session(
                    session_id=self.session_id,
                    workflow_name="hybrid_search",
                    status="running",
                    metadata={
                        "query": query,
                        "include_rag": include_rag,
                        "include_web": include_web,
                        "max_results": max_results
                    }
                )

                # Detect query language and set language instruction
                self.detected_language, confidence = language_detector.detect_language(query)
                self.language_instruction = language_detector.get_language_instruction(self.detected_language)

                language_name = language_detector.get_language_name(self.detected_language)
                print(f"Detected language: {language_name} ({self.detected_language}) with confidence: {confidence:.2f}")

                # Initialize search session
                await self._initialize_search_session(query)

                # Optimized parallel execution for RAG and Web search
                if include_rag and include_web:
                    await self._broadcast_progress("Search Orchestrator", "started",
                                                 "Running RAG and Web search in parallel...")

                    # Run RAG and Web search concurrently for better performance
                    rag_task = asyncio.create_task(self._run_agent_with_progress(
                        self.rag_agent, query, "RAG Specialist"))
                    web_task = asyncio.create_task(self._run_agent_with_progress(
                        self.web_agent, query, "Web Search Specialist"))

                    # Wait for both to complete
                    rag_result, web_result = await asyncio.gather(rag_task, web_task, return_exceptions=True)

                    # Handle exceptions
                    if isinstance(rag_result, Exception):
                        await self._broadcast_progress("RAG Specialist", "failed", f"RAG search failed: {str(rag_result)}")
                        rag_result = None
                    if isinstance(web_result, Exception):
                        await self._broadcast_progress("Web Search Specialist", "failed", f"Web search failed: {str(web_result)}")
                        web_result = None

                    # Combine results for synthesis
                    combined_context = self._combine_search_results(rag_result, web_result, query)

                elif include_rag:
                    await self._broadcast_progress("Search Orchestrator", "started", "Running RAG search only...")
                    rag_result = await self._run_agent_with_progress(self.rag_agent, query, "RAG Specialist")
                    combined_context = self._combine_search_results(rag_result, None, query)

                elif include_web:
                    await self._broadcast_progress("Search Orchestrator", "started", "Running Web search only...")
                    web_result = await self._run_agent_with_progress(self.web_agent, query, "Web Search Specialist")
                    combined_context = self._combine_search_results(None, web_result, query)

                else:
                    combined_context = f"Query: {query}\n\nNo search sources enabled."

                # Extract sources first (needed for validation)
                all_sources = self._extract_sources_from_results([
                    rag_result if include_rag else None,
                    web_result if include_web else None
                ])

                # Run synthesis, validation, and answer generation in sequence (they depend on each other)
                logger.info("DEBUG: About to run synthesis agent")
                synthesis_result = await self._run_agent_with_progress(
                    self.synthesis_agent, combined_context, "Information Synthesizer")
                logger.info("DEBUG: Synthesis completed, about to run validation")

                # Use the validation agent's specialized method instead of generic arun
                await self._broadcast_progress("Information Validator", "started", "Information Validator is processing...")
                try:
                    logger.info(f"DEBUG: Calling validation agent with {len(all_sources)} sources")
                    validation_result = await self.validation_agent.validate_information(
                        synthesis=synthesis_result.content if synthesis_result else combined_context,
                        sources=all_sources,
                        query=query
                    )
                    logger.info(f"DEBUG: Validation result type: {type(validation_result)}")
                    logger.info(f"DEBUG: Validation result keys: {validation_result.keys() if isinstance(validation_result, dict) else 'Not a dict'}")
                    if isinstance(validation_result, dict) and "analysis" in validation_result:
                        logger.info(f"DEBUG: Analysis confidence: {validation_result['analysis'].get('confidence_score', 'Not found')}")
                    await self._broadcast_progress("Information Validator", "completed", "Information Validator completed successfully")
                    logger.info("DEBUG: Validation completed successfully")
                except Exception as e:
                    logger.error(f"DEBUG: Validation error: {e}")
                    await self._broadcast_progress("Information Validator", "failed", f"Information Validator failed: {str(e)}")
                    raise e

                logger.info("DEBUG: About to prepare answer context")

                # Prepare context for answer generation including validation results
                answer_context = combined_context
                if validation_result and isinstance(validation_result, dict):
                    if "validation_report" in validation_result:
                        answer_context += f"\n\nValidation Report:\n{validation_result['validation_report']}"
                elif validation_result and hasattr(validation_result, 'content'):
                    answer_context += f"\n\nValidation Report:\n{validation_result.content}"

                final_answer = await self._run_agent_with_progress(
                    self.answer_agent, answer_context, "Answer Generator")

                # Sources already extracted earlier for validation

                processing_time = time.time() - self.start_time

                # Extract confidence and quality scores from validation and answer results
                confidence_score = None  # No default - must be calculated
                quality_score = None     # No default - must be calculated

                # Get confidence from validation result - access the actual analysis
                if validation_result:
                    # Check if validation_result is a dict with analysis
                    if isinstance(validation_result, dict) and "analysis" in validation_result:
                        confidence_score = validation_result["analysis"].get("confidence_score")
                        print(f"Got confidence from validation analysis (dict): {confidence_score}")
                    # Check if validation_result has analysis attribute
                    elif hasattr(validation_result, 'analysis') and validation_result.analysis:
                        confidence_score = validation_result.analysis.get("confidence_score")
                        print(f"Got confidence from validation analysis (attr): {confidence_score}")
                    # Fallback: try to extract from content if analysis not available
                    elif hasattr(validation_result, 'content'):
                        try:
                            import re
                            confidence_match = re.search(r'confidence[:\s]+([0-9]*\.?[0-9]+)', validation_result.content.lower())
                            if confidence_match:
                                confidence_score = min(max(float(confidence_match.group(1)), 0.1), 0.95)
                                print(f"Extracted confidence from content: {confidence_score}")
                        except Exception as e:
                            print(f"Error extracting confidence from content: {e}")
                    # Check if it's a dict with content
                    elif isinstance(validation_result, dict) and "validation_report" in validation_result:
                        try:
                            import re
                            content = validation_result["validation_report"].lower()
                            confidence_match = re.search(r'confidence[:\s]+([0-9]*\.?[0-9]+)', content)
                            if confidence_match:
                                confidence_score = min(max(float(confidence_match.group(1)), 0.1), 0.95)
                                print(f"Extracted confidence from dict content: {confidence_score}")
                        except Exception as e:
                            print(f"Error extracting confidence from dict content: {e}")

                # If still no confidence, calculate based on available information
                if confidence_score is None:
                    confidence_score = self._calculate_fallback_confidence(all_sources, synthesis_result, validation_result)
                    print(f"Calculated fallback confidence: {confidence_score}")

                # Get quality from answer result
                if final_answer and hasattr(final_answer, 'content'):
                    try:
                        answer_content = final_answer.content
                        quality_score = self._calculate_quality_score(answer_content, all_sources, confidence_score)
                        print(f"Calculated quality score: {quality_score}")
                    except Exception as e:
                        print(f"Error calculating quality score: {e}")
                        quality_score = confidence_score * 0.8  # Fallback based on confidence

                # Ensure we have valid scores
                if confidence_score is None:
                    confidence_score = 0.5
                    print("Using absolute fallback confidence: 0.5")
                if quality_score is None:
                    quality_score = confidence_score * 0.8
                    print(f"Using fallback quality based on confidence: {quality_score}")

                final_result = {
                    "query": query,
                    "answer": final_answer.content if final_answer else "Unable to generate answer",
                    "sources": all_sources,
                    "metadata": {
                        "agents_used": self._get_agents_used(include_rag, include_web),
                        "total_sources": len(all_sources),
                        "session_id": self.session_id,
                        "processing_time": f"{processing_time:.2f}s",
                        "include_rag": include_rag,
                        "include_web": include_web,
                        "max_results": max_results,
                        "parallel_execution": include_rag and include_web,
                        "detected_language": self.detected_language,
                        "language_name": language_detector.get_language_name(self.detected_language),
                        "confidence_score": confidence_score,
                        "quality_score": quality_score
                    }
                }

                # Store search results for future learning
                await self._store_search_results(query, final_result, all_sources)

                # Save search to database
                await database_service.save_search_history(
                    session_id=self.session_id,
                    query=query,
                    response=final_result.get("answer", ""),
                    sources=all_sources,
                    processing_time=processing_time
                )

                # Update workflow session as completed
                await database_service.save_agent_workflow_session(
                    session_id=self.session_id,
                    workflow_name="hybrid_search",
                    status="completed",
                    result=final_result
                )

                # Broadcast final result
                await self._broadcast_final_result(final_result)

                return final_result

            except Exception as e:
                error_msg = f"Multi-agent search failed: {str(e)}"

                # Update workflow session as failed
                await database_service.save_agent_workflow_session(
                    session_id=self.session_id,
                    workflow_name="hybrid_search",
                    status="failed",
                    result={"error": error_msg}
                )

                await self.progress_manager.broadcast_error(self.session_id, error_msg)
                raise e
    
    async def _run_agent_with_progress(self, agent, message: str, agent_name: str):
        """Run an agent with optimized progress tracking"""
        start_time = time.time()

        try:
            await self._broadcast_progress(agent_name, "started", f"{agent_name} is processing...")

            # Log agent execution start
            await database_service.save_agent_execution_log(
                session_id=self.session_id,
                agent_name=agent_name,
                status="started",
                input_data={"message": message[:500]}  # Truncate long messages
            )

            # Add language instruction to the message
            language_aware_message = f"{self.language_instruction}\n\n{message}"

            # Run agent without excessive streaming overhead
            result = await agent.arun(language_aware_message)

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Log agent execution completion
            await database_service.save_agent_execution_log(
                session_id=self.session_id,
                agent_name=agent_name,
                status="completed",
                output_data={"result": str(result)[:500] if result else ""},  # Truncate long results
                execution_time_ms=execution_time_ms
            )

            await self._broadcast_progress(agent_name, "completed",
                                         f"{agent_name} completed successfully")
            return result

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Log agent execution failure
            await database_service.save_agent_execution_log(
                session_id=self.session_id,
                agent_name=agent_name,
                status="failed",
                error_message=str(e),
                execution_time_ms=execution_time_ms
            )

            await self._broadcast_progress(agent_name, "failed", f"{agent_name} failed: {str(e)}")
            raise e

    async def _broadcast_progress(self, agent_name: str, status: str, message: str):
        """Optimized progress broadcasting with reduced frequency"""
        if self.session_id:
            await self.progress_manager.broadcast_progress(
                self.session_id,
                {
                    "agent": agent_name,
                    "status": status,
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                }
            )

    def _combine_search_results(self, rag_result, web_result, query: str) -> str:
        """Combine RAG and web search results into a coherent context"""
        context_parts = [f"Query: {query}\n"]

        if rag_result and hasattr(rag_result, 'content'):
            context_parts.append(f"RAG Search Results:\n{rag_result.content}\n")

        if web_result and hasattr(web_result, 'content'):
            context_parts.append(f"Web Search Results:\n{web_result.content}\n")

        return "\n".join(context_parts)

    def _extract_sources_from_results(self, results: List) -> List[Dict[str, Any]]:
        """Extract sources from agent results"""
        all_sources = []

        for result in results:
            if result and hasattr(result, 'content'):
                # Check if this is a web search result with structured data
                if hasattr(result, 'search_results') and result.search_results:
                    # Use structured search results if available
                    for search_result in result.search_results:
                        all_sources.append({
                            "title": search_result.get("title", "Source from search"),
                            "url": search_result.get("url", ""),
                            "content": search_result.get("content", "")[:300] + "..." if len(search_result.get("content", "")) > 300 else search_result.get("content", ""),
                            "relevance_score": search_result.get("relevance_score", 0.8),
                            "source_type": search_result.get("source_type", "web_search")
                        })
                else:
                    # Fallback to simple URL extraction from content
                    import re
                    # Fixed regex pattern that doesn't include trailing punctuation
                    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|(?:%[0-9a-fA-F][0-9a-fA-F]))+(?=[^\w]|$)',
                                    result.content)
                    # Clean up URLs by removing trailing punctuation
                    cleaned_urls = []
                    for url in urls:
                        # Remove trailing punctuation like ), ., etc.
                        url = re.sub(r'[)\].,;!?]+$', '', url)
                        cleaned_urls.append(url)
                    for url in cleaned_urls:
                        all_sources.append({
                            "title": f"Source from search",
                            "url": url,
                            "content": "",
                            "relevance_score": 0.8,
                            "source_type": "extracted"
                        })

        return all_sources

    async def _initialize_search_session(self, query: str):
        """Initialize the search session"""
        if self.session_id:
            await self._broadcast_progress("Search Orchestrator", "started",
                                         f"Initializing multi-agent search for: {query[:50]}...")
    
    async def _broadcast_final_result(self, result: Dict[str, Any]):
        """Broadcast the final result"""
        if self.session_id:
            await self.progress_manager.broadcast_result(
                self.session_id,
                {
                    "type": "final_result",
                    "status": "completed",
                    "result": result["answer"],
                    "sources": result["sources"],
                    "metadata": result["metadata"]
                }
            )
    
    def _get_agents_used(self, include_rag: bool, include_web: bool) -> List[str]:
        """Get list of agents used in the search"""
        agents = []
        if include_rag:
            agents.append("RAG Specialist")
        if include_web:
            agents.append("Web Search Specialist")
        agents.extend(["Information Synthesizer", "Information Validator", "Answer Generator"])
        return agents

    def _calculate_quality_score(self, answer_content: str, sources: List[Dict[str, Any]], confidence_score: float) -> float:
        """Calculate quality score based on answer characteristics"""
        quality_score = 0.3  # Base score

        # Content length factor
        word_count = len(answer_content.split())
        if word_count > 100:
            quality_score += 0.1
        if word_count > 300:
            quality_score += 0.05

        # Citation factor
        citation_indicators = ["source:", "according to", "based on", "reference:", "[", "]", "http", "www.", ".com", ".org"]
        has_citations = any(indicator in answer_content.lower() for indicator in citation_indicators)
        if has_citations:
            quality_score += 0.2

        # Structure factor
        structure_indicators = ["#", "##", "###", "**", "*", "1.", "2.", "3.", "•", "-"]
        has_structure = any(indicator in answer_content for indicator in structure_indicators)
        if has_structure:
            quality_score += 0.15

        # Source count factor
        if sources:
            source_count = len(sources)
            if source_count >= 3:
                quality_score += 0.1
            if source_count >= 5:
                quality_score += 0.05

        # Factor in confidence score
        quality_score = (quality_score * 0.7) + (confidence_score * 0.3)

        return min(max(quality_score, 0.1), 0.95)

    def _calculate_fallback_confidence(self, sources: List[Dict[str, Any]], synthesis_result=None, validation_result=None) -> float:
        """Calculate confidence when validation analysis is not available"""
        confidence = 0.3  # Start with low base confidence

        # Factor in source count and quality
        if sources:
            source_count = len(sources)
            if source_count >= 3:
                confidence += 0.2
            if source_count >= 5:
                confidence += 0.1

            # Check for high-quality domains
            high_quality_count = 0
            for source in sources:
                url = source.get('url', '').lower()
                quality_domains = [
                    'wikipedia.org', 'arxiv.org', 'nature.com', 'sciencedirect.com',
                    'pubmed.ncbi.nlm.nih.gov', 'scholar.google.com', 'jstor.org',
                    'reuters.com', 'bbc.com', 'cnn.com', 'nytimes.com', 'washingtonpost.com',
                    'gov', 'edu', 'org'
                ]
                if any(domain in url for domain in quality_domains):
                    high_quality_count += 1

            if source_count > 0:
                quality_ratio = high_quality_count / source_count
                confidence += quality_ratio * 0.3

        # Factor in synthesis quality if available
        if synthesis_result and hasattr(synthesis_result, 'content'):
            content = synthesis_result.content.lower()
            # Look for positive indicators
            positive_indicators = ['confirmed', 'verified', 'consistent', 'reliable', 'accurate']
            negative_indicators = ['uncertain', 'unclear', 'conflicting', 'unverified', 'disputed']

            positive_count = sum(1 for indicator in positive_indicators if indicator in content)
            negative_count = sum(1 for indicator in negative_indicators if indicator in content)

            confidence += (positive_count * 0.05)
            confidence -= (negative_count * 0.1)

        return min(max(confidence, 0.1), 0.9)

    async def _store_search_results(self, query: str, final_result: Dict[str, Any], sources: List[Dict[str, Any]]):
        """Store search results in vector database for future learning using vector embedding service"""
        try:
            # Store the final answer as a document using vector embedding service
            answer_content = final_result.get("answer", "")
            if answer_content and len(answer_content.strip()) > 50:
                answer_metadata = {
                    "type": "search_result",
                    "query": query,
                    "session_id": self.session_id,
                    "language": self.detected_language,
                    "confidence_score": final_result.get("metadata", {}).get("confidence_score", 0.7),
                    "quality_score": final_result.get("metadata", {}).get("quality_score", 0.7),
                    "agents_used": final_result.get("metadata", {}).get("agents_used", []),
                    "source_count": len(sources),
                    "created_at": datetime.now().isoformat()
                }

                # Use vector embedding service to store the answer
                await vector_embedding_service.store_document(answer_content, answer_metadata)
                print(f"Stored search result with vector embeddings for query: {query[:50]}...")

            # Store individual sources using vector embedding service
            if sources:
                # Prepare search results for vector storage
                search_results_for_storage = []
                for source in sources:
                    content = source.get("content", "")
                    if not content or len(content.strip()) < 50:
                        continue

                    search_result = {
                        "content": content,
                        "title": source.get("title", ""),
                        "url": source.get("url", ""),
                        "source": source.get("source_type", "web_search"),
                        "relevance_score": source.get("relevance_score", 0.5),
                        "timestamp": datetime.now().isoformat()
                    }
                    search_results_for_storage.append(search_result)

                # Use vector embedding service to store search results
                if search_results_for_storage:
                    # Limit to top 5 sources to avoid overwhelming the DB
                    limited_results = search_results_for_storage[:5]
                    await vector_embedding_service.store_search_results(limited_results, query)
                    print(f"Stored {len(limited_results)} source documents with vector embeddings from search")

        except Exception as e:
            print(f"Error storing search results: {e}")
            # Don't raise the error as this shouldn't break the search flow

    async def simple_search(self, query: str) -> str:
        """Simple search using the team (for compatibility)"""
        try:
            response = await self.team.arun(query, session_id=self.session_id)
            return response.content
        except Exception as e:
            return f"Search failed: {str(e)}"


def create_search_team(session_id: str = None) -> MultiAgentSearchTeam:
    """Create a multi-agent search team"""
    return MultiAgentSearchTeam(session_id=session_id)
