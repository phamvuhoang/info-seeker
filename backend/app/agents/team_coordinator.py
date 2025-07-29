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
        """Execute the multi-agent hybrid search workflow"""

        try:
            # Initialize search session
            await self._initialize_search_session(query)

            # Simplified team coordination following agno best practices
            # Let the team coordinate naturally without over-prescriptive instructions
            team_response = await self.team.arun(
                message=f"Please provide a comprehensive answer to this query: {query}",
                session_id=self.session_id
            )

            # Extract sources from team member runs if available
            all_sources = []
            agents_used = []

            if hasattr(team_response, 'member_runs') and team_response.member_runs:
                for member_run in team_response.member_runs:
                    if hasattr(member_run, 'agent') and member_run.agent:
                        agent_name = member_run.agent.name
                        agents_used.append(agent_name)

                        # Extract any sources from agent responses
                        if hasattr(member_run, 'messages'):
                            for message in member_run.messages:
                                if hasattr(message, 'content'):
                                    # Simple source extraction - look for URLs or structured data
                                    content = message.content
                                    if "http" in content:
                                        # Extract URLs as sources
                                        import re
                                        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content)
                                        for url in urls:
                                            all_sources.append({
                                                "title": f"Source from {agent_name}",
                                                "url": url,
                                                "agent": agent_name,
                                                "relevance_score": 0.8
                                            })
            
            # Compile final result - simplified and focused on actual team output
            final_result = {
                "query": query,
                "answer": team_response.content,
                "sources": all_sources,
                "metadata": {
                    "agents_used": agents_used if agents_used else ["InfoSeeker Search Team"],
                    "total_sources": len(all_sources),
                    "session_id": self.session_id,
                    "include_rag": include_rag,
                    "include_web": include_web,
                    "max_results": max_results
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
