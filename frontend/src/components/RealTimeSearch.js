import React, { useState, useEffect, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import {
  SearchSSE,
  DEFAULT_AGENTS,
  AGENT_STATUS,
  getAgentStatusColor,
  getAgentStatusIcon,
  calculateProgress
} from '../services/websocket';
import { Search, Loader2, AlertCircle, CheckCircle, Clock, ChevronDown, ChevronUp, Maximize2, Minimize2, Brain } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const RealTimeSearch = () => {
  const [query, setQuery] = useState('');
  const [sessionId] = useState(() => uuidv4());
  const [isSearching, setIsSearching] = useState(false);
  const [agentProgress, setAgentProgress] = useState([]);
  const [reasoningSteps, setReasoningSteps] = useState([]);
  const [finalResult, setFinalResult] = useState('');
  const [sources, setSources] = useState([]);
  const [metadata, setMetadata] = useState(null);
  const [error, setError] = useState('');
  const [searchStartTime, setSearchStartTime] = useState(null);
  const [expandedAgents, setExpandedAgents] = useState(new Set());
  const [autoScroll, setAutoScroll] = useState(true);
  const wsRef = useRef(null);
  const agentProgressRef = useRef(null);
  const reasoningStepsRef = useRef(null);

  const initializeAgents = () => {
    setAgentProgress([...DEFAULT_AGENTS]);
    setExpandedAgents(new Set());
  };

  const toggleAgentExpansion = (agentName) => {
    setExpandedAgents(prev => {
      const newSet = new Set(prev);
      if (newSet.has(agentName)) {
        newSet.delete(agentName);
      } else {
        newSet.add(agentName);
      }
      return newSet;
    });
  };

  const scrollToBottom = (ref) => {
    if (autoScroll && ref.current) {
      setTimeout(() => {
        ref.current.scrollTop = ref.current.scrollHeight;
      }, 100);
    }
  };

  const handleProgress = (update) => {
    console.log('Progress update received:', update);

    // Handle both direct format and nested data format
    const agentName = update.agent || update.data?.agent;
    const status = update.status || update.data?.status;
    const message = update.message || update.data?.message;
    const result = update.result_preview || update.result || update.data?.result;
    const timestamp = update.timestamp || update.data?.timestamp;
    const details = update.details || update.data?.details;

    if (agentName) {
      // Batch state updates for better performance
      setAgentProgress(prev => {
        const updated = prev.map(agent =>
          agent.name === agentName
            ? {
                ...agent,
                status: status || agent.status,
                message: message || agent.message,
                result: result,
                timestamp: timestamp,
                details: details,
                lastUpdated: Date.now()
              }
            : agent
        );
        return updated;
      });

      // Add reasoning steps for all status changes with details
      if (status && (status === 'started' || status === 'completed' || status === 'failed' || status === 'processing' || status === 'rate_limited')) {
        setReasoningSteps(prev => {
          const newStep = {
            id: Date.now() + Math.random(),
            agent: agentName,
            message: message,
            timestamp: timestamp || new Date().toISOString(),
            type: status,
            details: details,
            important: status === 'started' || status === 'completed' || status === 'failed' || status === 'rate_limited'
          };

          const newSteps = [...prev, newStep];

          // Limit reasoning steps to prevent memory issues
          const limitedSteps = newSteps.slice(-50);

          // Debounced auto-scroll
          if (autoScroll) {
            setTimeout(() => scrollToBottom(reasoningStepsRef), 200);
          }
          return limitedSteps;
        });
      }

      // Debounced auto-scroll for agent progress
      if (autoScroll) {
        setTimeout(() => scrollToBottom(agentProgressRef), 200);
      }
    }
  };

  const handleResult = (result) => {
    console.log('Final result received:', result);

    setFinalResult(result.result || result.data?.result || '');
    setSources(result.sources || result.data?.sources || []);
    setMetadata(result.metadata || result.data?.metadata);
    setIsSearching(false);
    setError('');
  };

  const handleError = (errorMessage) => {
    console.error('Search error:', errorMessage);
    setError(errorMessage);
    setIsSearching(false);
  };

  const startSearch = async () => {
    if (!query.trim()) return;

    setIsSearching(true);
    setFinalResult('');
    setSources([]);
    setMetadata(null);
    setError('');
    setReasoningSteps([]);
    setSearchStartTime(new Date());
    initializeAgents();

    // Connect SSE
    wsRef.current = new SearchSSE(
      sessionId,
      handleProgress,
      handleResult,
      handleError
    );
    wsRef.current.connect();

    // Start search
    try {
      const response = await fetch('/api/v1/search/hybrid', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          session_id: sessionId,
          include_web: true,
          include_rag: true,
          max_results: 10
        }),
      });

      if (!response.ok) {
        throw new Error('Search request failed');
      }

      const data = await response.json();
      console.log('Search initiated:', data);
    } catch (error) {
      handleError('Failed to start search: ' + error.message);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !isSearching && query.trim()) {
      startSearch();
    }
  };

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.disconnect();
      }
    };
  }, []);

  const progress = calculateProgress(agentProgress);
  const searchDuration = searchStartTime ? 
    Math.round((new Date() - searchStartTime) / 1000) : 0;

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Hero Section */}
      <div className="mb-12 text-center">
        <div className="mb-8">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Multi-Agent AI Search
          </h1>
          <p className="text-xl text-gray-600 mb-6 max-w-3xl mx-auto">
            Experience the power of specialized AI agents working together to deliver comprehensive,
            accurate answers by combining knowledge base search with real-time web information.
          </p>

          {/* Agent Team Overview */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 max-w-4xl mx-auto mb-8">
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 p-4 rounded-lg border border-blue-200">
              <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center mx-auto mb-2">
                <Search className="w-4 h-4 text-white" />
              </div>
              <div className="text-sm font-medium text-blue-900">RAG Specialist</div>
              <div className="text-xs text-blue-700">Knowledge Base</div>
            </div>
            <div className="bg-gradient-to-br from-green-50 to-green-100 p-4 rounded-lg border border-green-200">
              <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-2">
                <Search className="w-4 h-4 text-white" />
              </div>
              <div className="text-sm font-medium text-green-900">Web Specialist</div>
              <div className="text-xs text-green-700">Real-time Search</div>
            </div>
            <div className="bg-gradient-to-br from-purple-50 to-purple-100 p-4 rounded-lg border border-purple-200">
              <div className="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center mx-auto mb-2">
                <Brain className="w-4 h-4 text-white" />
              </div>
              <div className="text-sm font-medium text-purple-900">Synthesizer</div>
              <div className="text-xs text-purple-700">Information Fusion</div>
            </div>
            <div className="bg-gradient-to-br from-orange-50 to-orange-100 p-4 rounded-lg border border-orange-200">
              <div className="w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center mx-auto mb-2">
                <CheckCircle className="w-4 h-4 text-white" />
              </div>
              <div className="text-sm font-medium text-orange-900">Validator</div>
              <div className="text-xs text-orange-700">Fact Checking</div>
            </div>
            <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 p-4 rounded-lg border border-indigo-200">
              <div className="w-8 h-8 bg-indigo-500 rounded-full flex items-center justify-center mx-auto mb-2">
                <Brain className="w-4 h-4 text-white" />
              </div>
              <div className="text-sm font-medium text-indigo-900">Answer Agent</div>
              <div className="text-xs text-indigo-700">Final Response</div>
            </div>
          </div>
        </div>

        {/* Search Input */}
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-6 h-6" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me anything... (e.g., 'What are the latest AI developments?' or 'Best places to visit in Ho Chi Minh City')"
                className="w-full pl-12 pr-4 py-5 text-lg border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-lg transition-all duration-200"
                disabled={isSearching}
              />
            </div>
            <button
              onClick={startSearch}
              disabled={isSearching || !query.trim()}
              className="px-8 py-5 bg-gradient-to-r from-blue-600 to-blue-700 text-white text-lg font-medium rounded-xl hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg flex items-center gap-3"
            >
              {isSearching ? (
                <>
                  <Loader2 className="w-6 h-6 animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="w-6 h-6" />
                  Search
                </>
              )}
            </button>
          </div>

          {/* Example Queries */}
          {!isSearching && !finalResult && (
            <div className="mt-6">
              <div className="text-sm text-gray-600 mb-3">Try these example queries:</div>
              <div className="flex flex-wrap gap-2 justify-center">
                {[
                  "Latest developments in artificial intelligence",
                  "Best tourist attractions in Ho Chi Minh City",
                  "Python programming best practices",
                  "Machine learning techniques for beginners"
                ].map((example, idx) => (
                  <button
                    key={idx}
                    onClick={() => setQuery(example)}
                    className="px-4 py-2 bg-gray-100 text-gray-700 rounded-full text-sm hover:bg-gray-200 transition-colors"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Features Section - Show when not searching and no results */}
      {!isSearching && !finalResult && (
        <div className="mb-12">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">How It Works</h2>
            <p className="text-gray-600 max-w-2xl mx-auto">
              Our multi-agent system combines the best of both worlds: comprehensive knowledge base search
              and real-time web information to deliver accurate, up-to-date answers.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Search className="w-8 h-8 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Intelligent Search</h3>
              <p className="text-gray-600">
                Our RAG specialist searches through curated knowledge bases while the web specialist
                finds the latest information online.
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Brain className="w-8 h-8 text-purple-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Smart Synthesis</h3>
              <p className="text-gray-600">
                Information is intelligently combined and validated by specialized agents to ensure
                accuracy and completeness.
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-8 h-8 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Real-time Updates</h3>
              <p className="text-gray-600">
                Watch as each agent works in real-time, providing transparency into the search
                and reasoning process.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="mb-8 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <div className="text-red-700">{error}</div>
        </div>
      )}

      {/* Progress Overview */}
      {isSearching && (
        <div className="mb-8 p-6 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-blue-900">Search Progress</h3>
            <div className="flex items-center gap-4 text-sm text-blue-700">
              <button
                onClick={() => setAutoScroll(!autoScroll)}
                className={`flex items-center gap-1 px-2 py-1 rounded ${
                  autoScroll ? 'bg-blue-200 text-blue-800' : 'bg-gray-200 text-gray-600'
                }`}
                title={autoScroll ? 'Disable auto-scroll' : 'Enable auto-scroll'}
              >
                {autoScroll ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
                Auto-scroll
              </button>
              <div className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {searchDuration}s
              </div>
              <div>{progress}% Complete</div>
            </div>
          </div>
          
          {/* Progress Bar */}
          <div className="w-full bg-blue-200 rounded-full h-2 mb-4">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Agent Progress */}
      {isSearching && agentProgress.length > 0 && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Agent Activity</h3>
          <div
            ref={agentProgressRef}
            className={`space-y-3 max-h-96 overflow-y-auto ${autoScroll ? 'auto-scroll-active' : ''}`}
            style={{ scrollBehavior: 'smooth' }}
          >
            {agentProgress.map((agent, index) => {
              const isExpanded = expandedAgents.has(agent.name);
              return (
                <div key={index} className="p-4 bg-gray-50 rounded-lg border">
                  <div className="flex items-center gap-4">
                    <div className={`w-4 h-4 rounded-full flex items-center justify-center text-white text-xs font-bold ${getAgentStatusColor(agent.status)}`}>
                      {getAgentStatusIcon(agent.status)}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">{agent.name}</div>
                      <div className="text-sm text-gray-600">{agent.message}</div>
                      {agent.timestamp && (
                        <div className="text-xs text-gray-400 mt-1">
                          {new Date(agent.timestamp).toLocaleTimeString()}
                        </div>
                      )}
                    </div>
                    {agent.result && (
                      <button
                        onClick={() => toggleAgentExpansion(agent.name)}
                        className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                      >
                        {isExpanded ? (
                          <>
                            <ChevronUp className="w-3 h-3" />
                            Collapse
                          </>
                        ) : (
                          <>
                            <ChevronDown className="w-3 h-3" />
                            Expand
                          </>
                        )}
                      </button>
                    )}
                  </div>

                  {/* Detailed Information */}
                  {agent.details && (
                    <div className="mt-3 p-3 bg-white rounded border">
                      <div className="font-medium mb-2 text-sm text-gray-700">Details:</div>

                      {/* RAG Search Results */}
                      {agent.details.top_results && (
                        <div className="mb-3">
                          <div className="text-xs font-medium text-gray-600 mb-1">
                            Found {agent.details.total_results} documents in knowledge base:
                          </div>
                          <div className="space-y-1">
                            {agent.details.top_results.slice(0, 3).map((result, idx) => (
                              <div key={idx} className="text-xs bg-gray-50 p-2 rounded">
                                <div className="font-medium text-gray-800">{result.title}</div>
                                <div className="text-gray-600">Similarity: {result.similarity_score}</div>
                                <div className="text-gray-500 mt-1">{result.content_preview}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Web Search Results */}
                      {agent.details.top_results && agent.name === 'Web Search Specialist' && (
                        <div className="mb-3">
                          <div className="text-xs font-medium text-gray-600 mb-1">
                            Found {agent.details.total_results} web results:
                          </div>
                          <div className="space-y-1">
                            {agent.details.top_results.slice(0, 3).map((result, idx) => (
                              <div key={idx} className="text-xs bg-gray-50 p-2 rounded">
                                <div className="font-medium text-gray-800">{result.title}</div>
                                <div className="text-blue-600 text-xs">{result.url}</div>
                                <div className="text-gray-600">Relevance: {result.relevance_score}</div>
                                <div className="text-gray-500 mt-1">{result.content_preview}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Synthesis Information */}
                      {agent.details.synthesis_analysis && (
                        <div className="mb-3">
                          <div className="text-xs font-medium text-gray-600 mb-1">Synthesis Analysis:</div>
                          <div className="text-xs bg-gray-50 p-2 rounded">
                            <div>Word count: {agent.details.synthesis_analysis.word_count}</div>
                            <div>Has citations: {agent.details.synthesis_analysis.has_citations ? 'Yes' : 'No'}</div>
                            <div>Structured content: {agent.details.synthesis_analysis.has_structured_content ? 'Yes' : 'No'}</div>
                            <div>Total sources: {agent.details.total_sources}</div>
                          </div>
                        </div>
                      )}

                      {/* Search Query */}
                      {agent.details.search_query && (
                        <div className="mb-2">
                          <div className="text-xs font-medium text-gray-600">Query:</div>
                          <div className="text-xs text-gray-700 bg-gray-50 p-1 rounded">{agent.details.search_query}</div>
                        </div>
                      )}

                      {/* No Results Reason */}
                      {agent.details.reason && (
                        <div className="mb-2">
                          <div className="text-xs font-medium text-gray-600">Reason:</div>
                          <div className="text-xs text-gray-700">{agent.details.reason}</div>
                        </div>
                      )}
                    </div>
                  )}

                  {agent.result && (
                    <div className="mt-3 p-3 bg-white rounded border">
                      <div className="font-medium mb-2 text-sm text-gray-700">Result:</div>
                      <div className={`text-sm text-gray-800 expandable-content ${
                        isExpanded
                          ? 'max-h-none'
                          : 'max-h-20 overflow-hidden'
                      }`}>
                        <ReactMarkdown className="prose-agent-result max-w-none">
                          {agent.result}
                        </ReactMarkdown>
                      </div>
                      {!isExpanded && agent.result.length > 100 && (
                        <div className="mt-2">
                          <button
                            onClick={() => toggleAgentExpansion(agent.name)}
                            className="text-xs text-blue-600 hover:text-blue-800"
                          >
                            Show more...
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Activity Timeline - Optimized */}
      {isSearching && reasoningSteps.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Activity Timeline</h3>
            <div className="text-sm text-gray-600">
              {reasoningSteps.filter(step => step.important).length} key events
            </div>
          </div>
          <div
            ref={reasoningStepsRef}
            className={`space-y-2 max-h-60 overflow-y-auto ${autoScroll ? 'auto-scroll-active' : ''}`}
            style={{ scrollBehavior: 'smooth' }}
          >
            {reasoningSteps.filter(step => step.important).slice(-15).map((step) => (
              <div key={step.id} className={`flex items-start gap-3 p-3 rounded-lg border ${
                step.type === 'completed' ? 'bg-green-50 border-green-200' :
                step.type === 'failed' ? 'bg-red-50 border-red-200' :
                step.type === 'rate_limited' ? 'bg-yellow-50 border-yellow-200' :
                'bg-blue-50 border-blue-200'
              }`}>
                <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                  step.type === 'completed' ? 'bg-green-500' :
                  step.type === 'failed' ? 'bg-red-500' :
                  step.type === 'rate_limited' ? 'bg-yellow-500' :
                  'bg-blue-500'
                }`}></div>
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-medium ${
                    step.type === 'completed' ? 'text-green-900' :
                    step.type === 'failed' ? 'text-red-900' :
                    'text-blue-900'
                  }`}>{step.agent}</div>
                  <div className={`text-sm break-words ${
                    step.type === 'completed' ? 'text-green-800' :
                    step.type === 'failed' ? 'text-red-800' :
                    'text-blue-800'
                  }`}>{step.message}</div>

                  {/* Show summary details in timeline */}
                  {step.details && (
                    <div className="text-xs mt-2 space-y-1">
                      {step.details.total_results !== undefined && (
                        <div className={`${
                          step.type === 'completed' ? 'text-green-700' :
                          step.type === 'failed' ? 'text-red-700' :
                          'text-blue-700'
                        }`}>
                          {step.details.total_results} results found
                        </div>
                      )}
                      {step.details.synthesis_analysis && (
                        <div className={`${
                          step.type === 'completed' ? 'text-green-700' :
                          step.type === 'failed' ? 'text-red-700' :
                          'text-blue-700'
                        }`}>
                          {step.details.synthesis_analysis.word_count} words, {step.details.total_sources} sources
                        </div>
                      )}
                    </div>
                  )}

                  <div className={`text-xs mt-1 ${
                    step.type === 'completed' ? 'text-green-600' :
                    step.type === 'failed' ? 'text-red-600' :
                    'text-blue-600'
                  }`}>
                    {new Date(step.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Final Result */}
      {finalResult && (
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="w-6 h-6 text-green-500" />
            <h3 className="text-xl font-semibold text-gray-900">Answer</h3>
          </div>
          <div className="prose max-w-none bg-white p-6 rounded-lg border shadow-sm">
            <ReactMarkdown>{finalResult}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Sources ({sources.length})</h3>
          <div className="grid gap-4">
            {sources.map((source, index) => (
              <div key={index} className="p-4 bg-gray-50 rounded-lg border">
                <div className="font-medium text-gray-900 mb-1">{source.title}</div>

                {/* Content preview */}
                {source.content && (
                  <p className="text-gray-700 text-sm mb-2 leading-relaxed">
                    {source.content}
                  </p>
                )}

                {/* URL for web sources */}
                {source.url && source.source_type !== 'knowledge_base' && (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 text-sm break-all block mb-2"
                  >
                    {source.url}
                  </a>
                )}

                {/* Additional info for DB sources */}
                {source.source_type === 'knowledge_base' && (
                  <div className="text-xs text-gray-500 mb-2">
                    {source.source && <span>Source: {source.source}</span>}
                    {source.document_id && <span className="ml-2">ID: {source.document_id.substring(0, 8)}...</span>}
                  </div>
                )}

                <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                  {source.relevance_score && (
                    <span>Relevance: {(source.relevance_score * 100).toFixed(1)}%</span>
                  )}
                  {source.similarity_score && (
                    <span>Similarity: {(source.similarity_score * 100).toFixed(1)}%</span>
                  )}
                  {source.source_type && (
                    <span className={`px-2 py-1 rounded text-xs ${
                      source.source_type === 'knowledge_base'
                        ? 'bg-green-100 text-green-800'
                        : source.source_type === 'web_search'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-gray-200 text-gray-800'
                    }`}>
                      {source.source_type === 'knowledge_base'
                        ? 'Source from DB'
                        : source.source_type === 'web_search'
                        ? 'Source from search'
                        : source.source_type === 'extracted'
                        ? 'Source from search'
                        : source.source_type}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Metadata */}
      {metadata && (
        <div className="text-sm text-gray-600 p-4 bg-gray-50 rounded-lg">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <span className="font-medium">Agents used:</span>
              <div>{metadata.agents_used?.join(', ')}</div>
            </div>
            <div>
              <span className="font-medium">Sources:</span>
              <div>{metadata.total_sources || 0}</div>
            </div>
            <div>
              <span className="font-medium">Confidence:</span>
              <div>{((metadata.confidence_score || 0) * 100).toFixed(1)}%</div>
            </div>
            <div>
              <span className="font-medium">Quality:</span>
              <div>{((metadata.quality_score || 0) * 100).toFixed(1)}%</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RealTimeSearch;
