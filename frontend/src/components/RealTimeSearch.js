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
import { Search, Loader2, AlertCircle, CheckCircle, Clock, ChevronDown, ChevronUp, Maximize2, Minimize2 } from 'lucide-react';
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

    if (agentName) {
      setAgentProgress(prev =>
        prev.map(agent =>
          agent.name === agentName
            ? {
                ...agent,
                status: status || agent.status,
                message: message || agent.message,
                result: result,
                timestamp: timestamp
              }
            : agent
        )
      );

      // Add reasoning steps for detailed progress
      if (update.event_type === 'reasoning_step' || status === 'reasoning') {
        setReasoningSteps(prev => {
          const newSteps = [...prev, {
            id: Date.now() + Math.random(),
            agent: agentName,
            message: message,
            timestamp: timestamp || new Date().toISOString(),
            type: 'reasoning'
          }];
          // Trigger auto-scroll for reasoning steps
          setTimeout(() => scrollToBottom(reasoningStepsRef), 100);
          return newSteps;
        });
      }

      // Trigger auto-scroll for agent progress
      setTimeout(() => scrollToBottom(agentProgressRef), 100);
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
    <div className="max-w-6xl mx-auto p-6">
      {/* Search Header */}
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          InfoSeeker Multi-Agent Search
        </h1>
        <p className="text-lg text-gray-600">
          AI-powered hybrid search with real-time agent collaboration
        </p>
      </div>

      {/* Search Input */}
      <div className="mb-8">
        <div className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask me anything..."
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-lg"
              disabled={isSearching}
            />
          </div>
          <button
            onClick={startSearch}
            disabled={isSearching || !query.trim()}
            className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-lg font-medium"
          >
            {isSearching ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <Search className="w-5 h-5" />
                Search
              </>
            )}
          </button>
        </div>
      </div>

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

      {/* Reasoning Steps */}
      {isSearching && reasoningSteps.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Reasoning Process</h3>
            <div className="text-sm text-gray-600">
              {reasoningSteps.length} steps
            </div>
          </div>
          <div
            ref={reasoningStepsRef}
            className={`space-y-2 max-h-80 overflow-y-auto ${autoScroll ? 'auto-scroll-active' : ''}`}
            style={{ scrollBehavior: 'smooth' }}
          >
            {reasoningSteps.slice(-20).map((step) => (
              <div key={step.id} className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-blue-900">{step.agent}</div>
                  <div className="text-sm text-blue-800 break-words">{step.message}</div>
                  <div className="text-xs text-blue-600 mt-1">
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
                {source.url && (
                  <a 
                    href={source.url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 text-sm break-all"
                  >
                    {source.url}
                  </a>
                )}
                <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                  {source.relevance_score && (
                    <span>Relevance: {(source.relevance_score * 100).toFixed(1)}%</span>
                  )}
                  {source.similarity_score && (
                    <span>Similarity: {(source.similarity_score * 100).toFixed(1)}%</span>
                  )}
                  {source.source_type && (
                    <span className="px-2 py-1 bg-gray-200 rounded text-xs">
                      {source.source_type}
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
