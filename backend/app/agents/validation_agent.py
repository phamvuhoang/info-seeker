from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from agno.tools.duckduckgo import DuckDuckGoTools
from typing import Dict, Any, List
import asyncio
import re
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

        # Add DuckDuckGo tools for fact-checking
        ddg_tools = DuckDuckGoTools(search=True, news=True, fixed_max_results=3)

        super().__init__(
            name="Information Validator",
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            description="Information validation specialist with fact-checking capabilities",
            instructions=[
                "You are the information validation specialist for InfoSeeker.",
                "Verify accuracy and consistency of synthesized information.",
                "Use web search tools to fact-check key claims when necessary.",
                "Check for potential biases or misinformation indicators.",
                "Assess source credibility and reliability.",
                "Flag any inconsistencies or concerns in the information.",
                "Evaluate the logical coherence of the synthesized response.",
                "Cross-reference information with multiple sources when possible.",
                "Identify areas where claims need additional verification.",
                "Provide detailed confidence scores with reasoning.",
                "Suggest improvements or corrections if needed.",
                "When in doubt, search for additional sources to verify claims.",
                "IMPORTANT: Always respond in the same language as the user's query.",
                "If you receive a language instruction at the beginning of the message, follow it strictly.",
                "Maintain the same language throughout your entire response."
            ],
            tools=[ddg_tools],
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

            # Extract key claims for fact-checking
            key_claims = self._extract_key_claims(synthesis)

            # Perform additional fact-checking if claims are found
            fact_check_results = await self._perform_fact_check(key_claims, query)

            # Create enhanced validation prompt with fact-checking instructions
            validation_prompt = f"""
Please perform a comprehensive validation of the following synthesized information:

Query: {query}

Synthesized Response:
{synthesis}

{validation_context}

VALIDATION METHODOLOGY:
1. FACTUAL ACCURACY: Cross-reference key claims against multiple sources
2. LOGICAL CONSISTENCY: Check for internal contradictions and logical flow
3. SOURCE CREDIBILITY: Evaluate the reliability and authority of cited sources
4. BIAS DETECTION: Identify potential biases, missing perspectives, or one-sided viewpoints
5. COMPLETENESS: Assess coverage of important aspects and identify gaps
6. TEMPORAL RELEVANCE: Check if information is current and up-to-date
7. CROSS-VERIFICATION: Look for corroboration across different source types

SPECIFIC VALIDATION TASKS:
- Identify any factual claims that need verification
- Check for contradictions between different sources
- Assess the credibility of each source (domain authority, publication date, author credentials)
- Look for potential biases in language, selection of facts, or omission of important information
- Evaluate if the response adequately addresses the original query
- Consider alternative viewpoints or interpretations that might be missing

CONFIDENCE SCORING CRITERIA:
- 0.9-1.0: Highly confident - Multiple reliable sources, no contradictions, comprehensive coverage
- 0.7-0.8: Confident - Good sources, minor inconsistencies, adequate coverage
- 0.5-0.6: Moderate confidence - Mixed source quality, some contradictions, partial coverage
- 0.3-0.4: Low confidence - Questionable sources, significant contradictions, incomplete
- 0.1-0.2: Very low confidence - Unreliable sources, major contradictions, inadequate

Please provide a detailed validation report with:
1. Overall Confidence Score (0.0-1.0)
2. Factual Accuracy Assessment
3. Source Reliability Analysis
4. Bias and Perspective Analysis
5. Completeness Evaluation
6. Specific Issues Found (if any)
7. Recommendations for Improvement

Be specific about any concerns and provide reasoning for your confidence score.
"""
            
            # Run validation
            response = await super().arun(validation_prompt)
            
            # Extract confidence score and issues
            validation_analysis = self._analyze_validation(response.content, sources)

            # Factor in fact-checking results
            if fact_check_results["claims_checked"] > 0:  # If fact-checking was actually performed
                # Weight the original confidence with fact-checking results
                original_confidence = validation_analysis["confidence_score"]
                fact_check_confidence = fact_check_results["overall_verification_score"]
                validation_analysis["confidence_score"] = (original_confidence * 0.6) + (fact_check_confidence * 0.4)
                validation_analysis["fact_check_performed"] = True
                validation_analysis["fact_check_results"] = fact_check_results
                print(f"Fact-checking performed: original={original_confidence:.3f}, fact_check={fact_check_confidence:.3f}, final={validation_analysis['confidence_score']:.3f}")
            else:
                validation_analysis["fact_check_performed"] = False
                print(f"No fact-checking performed, using base confidence: {validation_analysis['confidence_score']:.3f}")
            
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

        # Calculate confidence score based on multiple factors
        confidence_score = 0.5  # Base score

        # Extract explicit confidence score from report
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
                    confidence_score = min(max(score, 0), 1)
                    break

        # Adjust confidence based on validation indicators
        positive_indicators = ["accurate", "reliable", "consistent", "credible", "verified", "confirmed"]
        negative_indicators = ["inaccurate", "unreliable", "inconsistent", "biased", "unverified", "questionable", "contradictory"]

        positive_count = sum(1 for indicator in positive_indicators if indicator in report_lower)
        negative_count = sum(1 for indicator in negative_indicators if indicator in report_lower)

        # Adjust confidence based on indicators
        confidence_score += (positive_count * 0.05)  # Boost for positive indicators
        confidence_score -= (negative_count * 0.1)   # Reduce for negative indicators

        # Factor in source quality
        if sources:
            high_quality_sources = 0
            total_sources = len(sources)

            for source in sources:
                url = source.get('url', '').lower()
                # Check for high-quality domains
                quality_domains = [
                    'wikipedia.org', 'arxiv.org', 'nature.com', 'sciencedirect.com',
                    'pubmed.ncbi.nlm.nih.gov', 'scholar.google.com', 'jstor.org',
                    'reuters.com', 'bbc.com', 'cnn.com', 'nytimes.com', 'washingtonpost.com',
                    'gov', 'edu', 'org'
                ]

                if any(domain in url for domain in quality_domains):
                    high_quality_sources += 1

            if total_sources > 0:
                source_quality_ratio = high_quality_sources / total_sources
                confidence_score += (source_quality_ratio * 0.2)  # Up to 20% boost for quality sources

        # Ensure confidence is within bounds
        analysis["confidence_score"] = min(max(confidence_score, 0.1), 0.95)

        print(f"Validation analysis complete: confidence={analysis['confidence_score']:.3f}, positive_indicators={positive_count}, negative_indicators={negative_count}, sources={len(sources) if sources else 0}")
        
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

    def _extract_key_claims(self, content: str) -> List[str]:
        """Extract key factual claims that should be verified"""
        claims = []

        # Split content into sentences
        sentences = re.split(r'[.!?]+', content)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue

            # Look for sentences with factual indicators
            factual_indicators = [
                r'\d+%',  # Percentages
                r'\$\d+',  # Dollar amounts
                r'\d{4}',  # Years
                r'according to',
                r'studies show',
                r'research indicates',
                r'data shows',
                r'statistics reveal',
                r'reports suggest',
                r'experts say',
                r'scientists found',
                r'analysis shows'
            ]

            for indicator in factual_indicators:
                if re.search(indicator, sentence, re.IGNORECASE):
                    claims.append(sentence)
                    break

        return claims[:5]  # Limit to top 5 claims to avoid overwhelming the validation

    async def _perform_fact_check(self, claims: List[str], query: str) -> Dict[str, Any]:
        """Perform additional fact-checking on key claims"""
        fact_check_results = {
            "claims_checked": len(claims),
            "verification_results": [],
            "overall_verification_score": 0.5  # Start with neutral score, not default
        }

        if not claims:
            return fact_check_results

        try:
            # Create a fact-checking query
            fact_check_query = f"Verify facts about: {query} - checking claims about {', '.join(claims[:2])}"

            # Use the agent's built-in search capability
            verification_response = await super().arun(f"Please search for and verify these claims: {fact_check_query}")

            if verification_response and hasattr(verification_response, 'content'):
                # Analyze the verification response
                verification_content = verification_response.content.lower()

                # Look for verification indicators
                positive_verification = ['confirmed', 'verified', 'accurate', 'correct', 'true', 'supported']
                negative_verification = ['false', 'incorrect', 'disputed', 'unverified', 'contradicted']

                positive_count = sum(1 for indicator in positive_verification if indicator in verification_content)
                negative_count = sum(1 for indicator in negative_verification if indicator in verification_content)

                # Calculate verification score
                if positive_count > negative_count:
                    fact_check_results["overall_verification_score"] = min(0.8 + (positive_count * 0.05), 0.95)
                elif negative_count > positive_count:
                    fact_check_results["overall_verification_score"] = max(0.3 - (negative_count * 0.1), 0.1)
                else:
                    fact_check_results["overall_verification_score"] = 0.6

                fact_check_results["verification_results"].append({
                    "query": fact_check_query,
                    "result": verification_response.content[:200] + "..." if len(verification_response.content) > 200 else verification_response.content,
                    "positive_indicators": positive_count,
                    "negative_indicators": negative_count
                })

        except Exception as e:
            print(f"Fact-checking error: {e}")
            fact_check_results["overall_verification_score"] = 0.5  # Neutral score on error

        return fact_check_results

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
