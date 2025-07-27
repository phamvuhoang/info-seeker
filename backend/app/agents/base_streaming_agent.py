from agno.agent import Agent
from typing import Any
import logging
import asyncio
from datetime import datetime
from ..services.sse_manager import progress_manager

logger = logging.getLogger(__name__)


class BaseStreamingAgent(Agent):
    """Base agent class that provides streaming capabilities for detailed progress tracking"""

    def __init__(self, session_id: str = None, *args, **kwargs):
        # Enable reasoning for detailed streaming events
        kwargs.setdefault('reasoning', True)
        kwargs.setdefault('markdown', True)
        super().__init__(*args, **kwargs)
        self.session_id = session_id
    
    async def arun_with_streaming(self, message: str, **kwargs) -> Any:
        """Run agent with streaming enabled and provide detailed step-by-step updates"""
        try:
            # Send detailed processing steps
            await self._broadcast_step("🤔 Analyzing your request...")
            await asyncio.sleep(0.5)  # Small delay for UX

            await self._broadcast_step("🧠 Applying reasoning and domain knowledge...")
            await asyncio.sleep(0.5)

            await self._broadcast_step("⚡ Processing with AI model...")

            # Run the agent (try streaming first, fallback to regular)
            try:
                response_stream = await super().arun(
                    message,
                    stream=True,
                    stream_intermediate_steps=True,
                    show_full_reasoning=True,
                    **kwargs
                )

                # Process streaming events and broadcast them
                final_response = None
                event_count = 0
                async for event in response_stream:
                    event_count += 1
                    if self.session_id:
                        await self._broadcast_agent_event(event)

                    # Capture the final response
                    if hasattr(event, 'event') and event.event == "RunCompleted":
                        final_response = event

                # If no events were generated, fall back to regular execution
                if event_count == 0:
                    logger.info(f"No streaming events generated for {self.name}, falling back to regular execution")
                    final_response = await super().arun(message, **kwargs)

            except Exception as stream_error:
                logger.warning(f"Streaming failed for {self.name}, falling back to regular execution: {stream_error}")
                final_response = await super().arun(message, **kwargs)

            await self._broadcast_step("✅ Analysis complete!")

            return final_response

        except Exception as e:
            logger.error(f"Error in streaming agent {self.name}: {e}")
            raise e

    async def _broadcast_step(self, step_message: str):
        """Broadcast a reasoning step"""
        if self.session_id:
            await progress_manager.broadcast_progress(
                self.session_id,
                {
                    "agent": self.name,
                    "status": "reasoning",
                    "message": step_message,
                    "event_type": "reasoning_step",
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    async def _broadcast_agent_event(self, event):
        """Broadcast detailed agent events via SSE"""
        try:
            event_type = getattr(event, 'event', 'unknown')
            logger.debug(f"Processing event: {event_type} for agent {self.name}")

            event_data = {
                "agent": self.name,
                "event_type": event_type,
                "timestamp": getattr(event, 'created_at', None)
            }
            
            # Handle different event types
            if hasattr(event, 'event'):
                if event.event == "RunStarted":
                    event_data.update({
                        "status": "processing",
                        "message": f"{self.name} started processing...",
                        "model": getattr(event, 'model', ''),
                        "model_provider": getattr(event, 'model_provider', '')
                    })
                
                elif event.event == "RunResponseContent":
                    if hasattr(event, 'content') and event.content:
                        # Handle content properly - it might be a string or object
                        content_str = str(event.content) if event.content else ""
                        event_data.update({
                            "status": "streaming",
                            "message": f"{self.name} is generating response...",
                            "content_delta": content_str,
                            "thinking": getattr(event, 'thinking', None)
                        })
                
                elif event.event == "ReasoningStarted":
                    event_data.update({
                        "status": "reasoning",
                        "message": f"{self.name} started reasoning process..."
                    })
                
                elif event.event == "ReasoningStep":
                    reasoning_content = getattr(event, 'reasoning_content', '')
                    content = getattr(event, 'content', None)
                    event_data.update({
                        "status": "reasoning_step",
                        "message": f"{self.name} reasoning step",
                        "reasoning_content": str(reasoning_content) if reasoning_content else "",
                        "content": str(content) if content else ""
                    })

                elif event.event == "ReasoningCompleted":
                    content = getattr(event, 'content', None)
                    event_data.update({
                        "status": "reasoning_completed",
                        "message": f"{self.name} completed reasoning",
                        "content": str(content) if content else ""
                    })
                
                elif event.event == "ToolCallStarted":
                    tool = getattr(event, 'tool', None)
                    tool_name = tool.function.name if tool and hasattr(tool, 'function') else 'unknown'
                    event_data.update({
                        "status": "tool_call",
                        "message": f"{self.name} calling tool: {tool_name}",
                        "tool_name": tool_name
                    })
                
                elif event.event == "ToolCallCompleted":
                    tool = getattr(event, 'tool', None)
                    tool_name = tool.function.name if tool and hasattr(tool, 'function') else 'unknown'
                    content = getattr(event, 'content', None)
                    event_data.update({
                        "status": "tool_completed",
                        "message": f"{self.name} completed tool: {tool_name}",
                        "tool_name": tool_name,
                        "tool_result": str(content) if content else ""
                    })
            
            # Broadcast the detailed event
            await progress_manager.broadcast_progress(self.session_id, event_data)
            
        except Exception as e:
            # Don't let event broadcasting errors break the main flow
            logger.error(f"Error broadcasting agent event: {e}")
