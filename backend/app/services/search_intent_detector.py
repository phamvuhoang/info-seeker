"""
Search Intent Detection Service
Analyzes queries to determine optimal search strategy and target sites
"""

import re
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from app.services.site_config_service import site_config_service

logger = logging.getLogger(__name__)


@dataclass
class SearchIntent:
    """Represents detected search intent and recommended strategy"""
    use_rag: bool = True  # Always use RAG for knowledge base
    use_general_web: bool = True  # Use general web search
    use_site_specific: bool = False  # Use site-specific search
    recommended_sites: List[str] = None  # Recommended target sites
    confidence: float = 0.0  # Confidence score (0.0 to 1.0)
    reasoning: str = ""  # Explanation of the decision
    query_language: str = "en"  # Detected query language
    query_category: str = "general"  # Query category


class SearchIntentDetector:
    """Service for detecting search intent and recommending search strategies"""
    
    def __init__(self):
        # Keywords for different categories and sites
        self.site_keywords = {
            'otoriyose.net': {
                'japanese': ['お取り寄せ', 'おとりよせ', 'グルメ', '食品', '通販', '特産品', '名産品', '地方', '郷土料理'],
                'english': ['otoriyose', 'gourmet', 'specialty food', 'regional food', 'japanese food ordering']
            },
            'ippin.gnavi.co.jp': {
                'japanese': ['パン', 'ヤマザキ', '山崎製パン', 'ベーカリー', '食パン', 'パン屋', 'yamazaki'],
                'english': ['bread', 'yamazaki', 'bakery', 'japanese bread', 'sandwich bread']
            },
            'gurusuguri.com': {
                'japanese': ['ぐるすぐり', 'プレミアム', '高級食材', '厳選', '上質', 'グルメ通販'],
                'english': ['gurusuguri', 'premium', 'high-quality food', 'gourmet delivery', 'luxury food']
            }
        }
        
        # General food-related keywords that might benefit from site-specific search
        self.food_keywords = {
            'japanese': ['食べ物', '料理', '食品', '美味しい', 'おいしい', 'グルメ', 'レストラン', '食事', '味', '食材'],
            'english': ['food', 'cuisine', 'restaurant', 'delicious', 'tasty', 'gourmet', 'meal', 'dish', 'cooking', 'recipe']
        }
        
        # Keywords that suggest general web search is sufficient
        self.general_keywords = {
            'japanese': ['ニュース', '天気', '株価', '政治', '経済', '技術', '科学', '歴史', '文化'],
            'english': ['news', 'weather', 'stock', 'politics', 'economy', 'technology', 'science', 'history', 'culture']
        }
    
    async def detect_intent(self, query: str) -> SearchIntent:
        """
        Analyze query and detect optimal search intent
        
        Args:
            query: User's search query
            
        Returns:
            SearchIntent with recommended search strategy
        """
        query_lower = query.lower().strip()
        
        if not query_lower:
            return SearchIntent(
                use_rag=True,
                use_general_web=False,
                use_site_specific=False,
                confidence=0.0,
                reasoning="Empty query"
            )
        
        # Detect language
        language = self._detect_language(query)
        
        # Check for specific site matches
        site_matches = await self._detect_site_matches(query_lower, language)
        
        # Check for food-related content
        is_food_related = self._is_food_related(query_lower, language)
        
        # Check for general topics
        is_general_topic = self._is_general_topic(query_lower, language)
        
        # Determine search strategy
        intent = await self._determine_search_strategy(
            query=query,
            query_lower=query_lower,
            language=language,
            site_matches=site_matches,
            is_food_related=is_food_related,
            is_general_topic=is_general_topic
        )
        
        return intent
    
    def _detect_language(self, query: str) -> str:
        """Detect query language (simple heuristic)"""
        # Check for Japanese characters
        japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]')
        if japanese_pattern.search(query):
            return 'japanese'
        return 'english'
    
    async def _detect_site_matches(self, query_lower: str, language: str) -> Dict[str, float]:
        """Detect which sites are relevant for the query"""
        site_matches = {}
        
        for site_key, keywords in self.site_keywords.items():
            score = 0.0
            relevant_keywords = keywords.get(language, [])
            
            for keyword in relevant_keywords:
                if keyword.lower() in query_lower:
                    # Exact match gets higher score
                    if keyword.lower() == query_lower:
                        score += 1.0
                    # Partial match gets lower score
                    else:
                        score += 0.5
            
            if score > 0:
                # Normalize score based on query length and keyword count
                normalized_score = min(score / len(relevant_keywords), 1.0)
                site_matches[site_key] = normalized_score
        
        return site_matches
    
    def _is_food_related(self, query_lower: str, language: str) -> bool:
        """Check if query is food-related"""
        food_keywords = self.food_keywords.get(language, [])
        return any(keyword.lower() in query_lower for keyword in food_keywords)
    
    def _is_general_topic(self, query_lower: str, language: str) -> bool:
        """Check if query is about general topics that don't need site-specific search"""
        general_keywords = self.general_keywords.get(language, [])
        return any(keyword.lower() in query_lower for keyword in general_keywords)
    
    async def _determine_search_strategy(self, 
                                       query: str,
                                       query_lower: str, 
                                       language: str,
                                       site_matches: Dict[str, float],
                                       is_food_related: bool,
                                       is_general_topic: bool) -> SearchIntent:
        """Determine the optimal search strategy based on analysis"""
        
        # Always use RAG for knowledge base search
        use_rag = True
        use_general_web = True
        use_site_specific = False
        recommended_sites = []
        confidence = 0.5  # Default confidence
        reasoning_parts = []
        
        # High confidence site-specific matches
        if site_matches:
            high_confidence_sites = [site for site, score in site_matches.items() if score >= 0.7]
            medium_confidence_sites = [site for site, score in site_matches.items() if 0.3 <= score < 0.7]
            
            if high_confidence_sites:
                use_site_specific = True
                recommended_sites = high_confidence_sites
                confidence = 0.9
                reasoning_parts.append(f"High confidence match for sites: {', '.join(high_confidence_sites)}")
            elif medium_confidence_sites:
                use_site_specific = True
                recommended_sites = medium_confidence_sites
                confidence = 0.7
                reasoning_parts.append(f"Medium confidence match for sites: {', '.join(medium_confidence_sites)}")
        
        # Food-related queries without specific site matches
        elif is_food_related and not is_general_topic:
            # Get all active food-related sites
            active_sites = await site_config_service.get_active_sites()
            food_sites = [site_key for site_key, config in active_sites.items() 
                         if config.category in ['food_ordering', 'bread_products', 'premium_food']]
            
            if food_sites:
                use_site_specific = True
                recommended_sites = food_sites
                confidence = 0.6
                reasoning_parts.append(f"Food-related query, searching all food sites: {', '.join(food_sites)}")
        
        # General topics - stick to general web search
        elif is_general_topic:
            use_site_specific = False
            confidence = 0.8
            reasoning_parts.append("General topic query, using standard web search")
        
        # Default reasoning
        if not reasoning_parts:
            reasoning_parts.append("No specific site matches, using general search")
        
        # Determine query category
        if site_matches:
            category = "site_specific"
        elif is_food_related:
            category = "food"
        elif is_general_topic:
            category = "general"
        else:
            category = "unknown"
        
        return SearchIntent(
            use_rag=use_rag,
            use_general_web=use_general_web,
            use_site_specific=use_site_specific,
            recommended_sites=recommended_sites,
            confidence=confidence,
            reasoning="; ".join(reasoning_parts),
            query_language=language,
            query_category=category
        )
    
    async def get_search_recommendations(self, query: str) -> Dict[str, Any]:
        """Get detailed search recommendations for a query"""
        intent = await self.detect_intent(query)
        
        return {
            "query": query,
            "detected_language": intent.query_language,
            "category": intent.query_category,
            "recommendations": {
                "use_rag": intent.use_rag,
                "use_general_web": intent.use_general_web,
                "use_site_specific": intent.use_site_specific,
                "target_sites": intent.recommended_sites or []
            },
            "confidence": intent.confidence,
            "reasoning": intent.reasoning,
            "timestamp": "now"
        }


# Global instance
search_intent_detector = SearchIntentDetector()
