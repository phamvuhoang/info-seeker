import React, { useState } from 'react';
import { ExternalLink, Database, Globe, Target, ChevronDown, ChevronUp, Clock, Star } from 'lucide-react';

const EnhancedResultCard = ({ result, index }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const getSourceIcon = (source) => {
    if (source.includes('knowledge_base') || source.includes('rag')) {
      return <Database className="w-4 h-4 text-green-600" />;
    } else if (source.includes('site_specific') || source.includes('jina')) {
      return <Target className="w-4 h-4 text-orange-600" />;
    } else {
      return <Globe className="w-4 h-4 text-blue-600" />;
    }
  };

  const getSourceLabel = (source) => {
    if (source.includes('knowledge_base') || source.includes('rag')) {
      return 'Knowledge Base';
    } else if (source.includes('site_specific') || source.includes('jina')) {
      return 'Site-Specific';
    } else {
      return 'Web Search';
    }
  };

  const getSourceColor = (source) => {
    if (source.includes('knowledge_base') || source.includes('rag')) {
      return 'bg-green-100 text-green-800 border-green-200';
    } else if (source.includes('site_specific') || source.includes('jina')) {
      return 'bg-orange-100 text-orange-800 border-orange-200';
    } else {
      return 'bg-blue-100 text-blue-800 border-blue-200';
    }
  };

  const getSiteIcon = (url) => {
    if (url.includes('otoriyose.net')) return '🍱';
    if (url.includes('ippin.gnavi.co.jp')) return '🍞';
    if (url.includes('gurusuguri.com')) return '🍽️';
    return '🌐';
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return null;
    const date = new Date(timestamp);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const truncateContent = (content, maxLength = 200) => {
    if (!content || content.length <= maxLength) return content;
    return content.substring(0, maxLength) + '...';
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow duration-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-sm font-medium text-gray-500">#{index + 1}</span>
              <div className={`flex items-center space-x-1 px-2 py-1 rounded-full text-xs border ${getSourceColor(result.source)}`}>
                {getSourceIcon(result.source)}
                <span>{getSourceLabel(result.source)}</span>
              </div>
              {result.relevance_score && (
                <div className="flex items-center space-x-1 px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs">
                  <Star className="w-3 h-3" />
                  <span>{Math.round(result.relevance_score * 100)}%</span>
                </div>
              )}
            </div>
            
            <h3 className="text-lg font-semibold text-gray-900 mb-2 line-clamp-2">
              {result.title}
            </h3>
            
            {result.url && (
              <div className="flex items-center space-x-2 mb-2">
                <span className="text-lg">{getSiteIcon(result.url)}</span>
                <a
                  href={result.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-800 text-sm flex items-center space-x-1 hover:underline"
                >
                  <span className="truncate max-w-md">{result.url}</span>
                  <ExternalLink className="w-3 h-3 flex-shrink-0" />
                </a>
              </div>
            )}
          </div>
          
          {result.timestamp && (
            <div className="flex items-center space-x-1 text-xs text-gray-500 ml-4">
              <Clock className="w-3 h-3" />
              <span>{formatTimestamp(result.timestamp)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        <div className="text-gray-700 leading-relaxed">
          {isExpanded ? (
            <div className="whitespace-pre-wrap">{result.content}</div>
          ) : (
            <div>{truncateContent(result.content)}</div>
          )}
        </div>

        {/* Expand/Collapse Button */}
        {result.content && result.content.length > 200 && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="mt-3 flex items-center space-x-1 text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            {isExpanded ? (
              <>
                <ChevronUp className="w-4 h-4" />
                <span>Show Less</span>
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4" />
                <span>Show More</span>
              </>
            )}
          </button>
        )}

        {/* Metadata */}
        {result.metadata && Object.keys(result.metadata).length > 0 && (
          <div className="mt-4 pt-3 border-t border-gray-100">
            <details className="group">
              <summary className="cursor-pointer text-sm font-medium text-gray-600 hover:text-gray-800">
                Additional Information
              </summary>
              <div className="mt-2 text-xs text-gray-500 space-y-1">
                {Object.entries(result.metadata).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <span className="font-medium capitalize">{key.replace(/_/g, ' ')}:</span>
                    <span className="text-right max-w-xs truncate">
                      {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}
      </div>
    </div>
  );
};

const EnhancedResultsList = ({ results, title = "Search Results" }) => {
  const [sortBy, setSortBy] = useState('relevance');
  const [filterBy, setFilterBy] = useState('all');

  const sortedAndFilteredResults = React.useMemo(() => {
    let filtered = results;

    // Filter by source type
    if (filterBy !== 'all') {
      filtered = results.filter(result => {
        if (filterBy === 'knowledge_base') {
          return result.source.includes('knowledge_base') || result.source.includes('rag');
        } else if (filterBy === 'web') {
          return !result.source.includes('knowledge_base') && !result.source.includes('rag') && !result.source.includes('site_specific');
        } else if (filterBy === 'site_specific') {
          return result.source.includes('site_specific') || result.source.includes('jina');
        }
        return true;
      });
    }

    // Sort results
    return filtered.sort((a, b) => {
      if (sortBy === 'relevance') {
        return (b.relevance_score || 0) - (a.relevance_score || 0);
      } else if (sortBy === 'timestamp') {
        const aTime = a.timestamp ? new Date(a.timestamp).getTime() : 0;
        const bTime = b.timestamp ? new Date(b.timestamp).getTime() : 0;
        return bTime - aTime;
      }
      return 0;
    });
  }, [results, sortBy, filterBy]);

  const getSourceCounts = () => {
    const counts = {
      all: results.length,
      knowledge_base: 0,
      web: 0,
      site_specific: 0
    };

    results.forEach(result => {
      if (result.source.includes('knowledge_base') || result.source.includes('rag')) {
        counts.knowledge_base++;
      } else if (result.source.includes('site_specific') || result.source.includes('jina')) {
        counts.site_specific++;
      } else {
        counts.web++;
      }
    });

    return counts;
  };

  const sourceCounts = getSourceCounts();

  if (!results || results.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <Globe className="w-12 h-12 mx-auto mb-4 text-gray-300" />
        <p>No results found</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with filters */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <h2 className="text-xl font-semibold text-gray-900">
          {title} ({sortedAndFilteredResults.length})
        </h2>
        
        <div className="flex flex-col sm:flex-row gap-2">
          {/* Filter */}
          <select
            value={filterBy}
            onChange={(e) => setFilterBy(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Sources ({sourceCounts.all})</option>
            <option value="knowledge_base">Knowledge Base ({sourceCounts.knowledge_base})</option>
            <option value="web">Web Search ({sourceCounts.web})</option>
            <option value="site_specific">Site-Specific ({sourceCounts.site_specific})</option>
          </select>

          {/* Sort */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="relevance">Sort by Relevance</option>
            <option value="timestamp">Sort by Date</option>
          </select>
        </div>
      </div>

      {/* Results */}
      <div className="space-y-4">
        {sortedAndFilteredResults.map((result, index) => (
          <EnhancedResultCard
            key={`${result.url || result.title}-${index}`}
            result={result}
            index={index}
          />
        ))}
      </div>
    </div>
  );
};

export default EnhancedResultsList;
export { EnhancedResultCard };
