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
from ..utils.performance_monitor import performance_monitor
from .rag_agent import create_rag_agent
from .web_search_agent import create_web_search_agent
from .synthesis_agent import create_synthesis_agent
from .validation_agent import create_validation_agent
from .answer_agent import create_answer_agent


class MultiAgentSearchTeam:
    def __init__(self, session_id: str = None):
        self.session_id = session_id
        self.progress_manager = progress_manager
        self.start_time = None

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

                # Run synthesis, validation, and answer generation in sequence (they depend on each other)
                synthesis_result = await self._run_agent_with_progress(
                    self.synthesis_agent, combined_context, "Information Synthesizer")

                validation_result = await self._run_agent_with_progress(
                    self.validation_agent, synthesis_result.content if synthesis_result else combined_context,
                    "Information Validator")

                final_answer = await self._run_agent_with_progress(
                    self.answer_agent, validation_result.content if validation_result else combined_context,
                    "Answer Generator")

                # Extract sources and compile final result
                all_sources = self._extract_sources_from_results([
                    rag_result if include_rag else None,
                    web_result if include_web else None
                ])

                processing_time = time.time() - self.start_time

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
                        "parallel_execution": include_rag and include_web
                    }
                }

                # Broadcast final result
                await self._broadcast_final_result(final_result)

                return final_result

            except Exception as e:
                error_msg = f"Multi-agent search failed: {str(e)}"
                await self.progress_manager.broadcast_error(self.session_id, error_msg)
                raise e
    
    async def _run_agent_with_progress(self, agent, message: str, agent_name: str):
        """Run an agent with optimized progress tracking"""
        try:
            await self._broadcast_progress(agent_name, "started", f"{agent_name} is processing...")

            # Run agent without excessive streaming overhead
            result = await agent.arun(message)

            await self._broadcast_progress(agent_name, "completed",
                                         f"{agent_name} completed successfully")
            return result

        except Exception as e:
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
                # Simple URL extraction from content
                import re
                urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                                result.content)
                for url in urls:
                    all_sources.append({
                        "title": f"Source from search",
                        "url": url,
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
