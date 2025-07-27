from agno.team import Team
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from agno.tools.reasoning import ReasoningTools
from typing import Dict, Any, List
import asyncio
from datetime import datetime
from ..core.config import settings
from ..services.sse_manager import progress_manager
from .rag_agent import create_rag_agent
from .web_search_agent import create_web_search_agent
from .synthesis_agent import create_synthesis_agent
from .validation_agent import create_validation_agent
from .answer_agent import create_answer_agent


class MultiAgentSearchTeam:
    def __init__(self, session_id: str = None):
        self.session_id = session_id
        self.progress_manager = progress_manager
        
        # Create specialized agents
        self.rag_agent = create_rag_agent(session_id)
        self.web_agent = create_web_search_agent(session_id)
        self.synthesis_agent = create_synthesis_agent(session_id)
        self.validation_agent = create_validation_agent(session_id)
        self.answer_agent = create_answer_agent(session_id)
        
        # Create orchestrator agent
        self.orchestrator = self._create_orchestrator()
        
        # Create the team
        self.team = self._create_team()
    
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
                "Work together to provide comprehensive, accurate answers.",
                "Each agent contributes their specialized expertise.",
                "Maintain context and build upon previous agent outputs.",
                "Ensure high-quality, well-sourced final responses.",
                "Coordinate efficiently to minimize response time.",
                "Share information between agents as needed."
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
        """Execute the multi-agent hybrid search workflow"""
        
        try:
            # Initialize search session
            await self._initialize_search_session(query)
            
            # Step 1: RAG Search (if enabled)
            rag_results = None
            if include_rag:
                rag_results = await self.rag_agent.search_knowledge_base(query, max_results)
            
            # Step 2: Web Search (if enabled)
            web_results = None
            if include_web:
                web_results = await self.web_agent.perform_web_search(query, max_results)
            
            # Step 3: Information Synthesis
            synthesis_result = await self.synthesis_agent.synthesize_information(
                query, rag_results, web_results
            )
            
            # Step 4: Information Validation
            all_sources = []
            if rag_results and rag_results.get("results"):
                all_sources.extend(rag_results["results"])
            if web_results and web_results.get("results"):
                all_sources.extend(web_results["results"])
            
            validation_result = await self.validation_agent.validate_information(
                synthesis_result.get("synthesis", ""),
                all_sources,
                query
            )
            
            # Step 5: Final Answer Generation
            answer_result = await self.answer_agent.generate_final_answer(
                query,
                synthesis_result.get("synthesis", ""),
                validation_result,
                all_sources
            )
            
            # Compile final result
            final_result = {
                "query": query,
                "answer": answer_result.get("answer", ""),
                "sources": all_sources,
                "metadata": {
                    "agents_used": self._get_agents_used(include_rag, include_web),
                    "rag_results_count": len(rag_results.get("results", [])) if rag_results else 0,
                    "web_results_count": len(web_results.get("results", [])) if web_results else 0,
                    "total_sources": len(all_sources),
                    "confidence_score": validation_result.get("analysis", {}).get("confidence_score", 0.7),
                    "quality_score": answer_result.get("analysis", {}).get("quality_score", 0.7),
                    "processing_time": "calculated_time",  # Would calculate actual time
                    "session_id": self.session_id
                },
                "workflow_details": {
                    "rag_search": rag_results,
                    "web_search": web_results,
                    "synthesis": synthesis_result,
                    "validation": validation_result,
                    "answer_generation": answer_result
                }
            }
            
            # Broadcast final result
            await self._broadcast_final_result(final_result)
            
            return final_result
            
        except Exception as e:
            error_msg = f"Multi-agent search failed: {str(e)}"
            await self.progress_manager.broadcast_error(self.session_id, error_msg)
            raise e
    
    async def _initialize_search_session(self, query: str):
        """Initialize the search session"""
        if self.session_id:
            await self.progress_manager.broadcast_progress(
                self.session_id,
                {
                    "agent": "Search Orchestrator",
                    "status": "started",
                    "message": f"Initializing multi-agent search for: {query[:50]}...",
                    "query": query
                }
            )
    
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
