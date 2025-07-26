import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Clock, ExternalLink, Star } from 'lucide-react';

const SearchResults = ({ results, loading, query }) => {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-pulse-slow">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            <p className="mt-4 text-gray-600">Searching for information...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!results) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Query and Processing Time */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Search Results for: "{query}"
          </h2>
          <div className="flex items-center text-sm text-gray-500">
            <Clock className="h-4 w-4 mr-1" />
            {results.processing_time?.toFixed(2)}s
          </div>
        </div>
      </div>

      {/* AI Answer */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center mb-4">
          <div className="bg-primary-100 rounded-full p-2 mr-3">
            <span className="text-primary-600 font-semibold text-sm">AI</span>
          </div>
          <h3 className="text-lg font-semibold text-gray-900">Answer</h3>
        </div>
        
        <div className="prose prose-blue max-w-none">
          <ReactMarkdown>{results.answer}</ReactMarkdown>
        </div>
      </div>

      {/* Sources */}
      {results.sources && results.sources.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Sources</h3>
          <div className="space-y-4">
            {results.sources.map((source, index) => (
              <div key={index} className="border border-gray-100 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h4 className="font-medium text-gray-900 mb-2">
                      {source.title}
                    </h4>
                    <p className="text-gray-600 text-sm mb-3">
                      {source.content}
                    </p>
                    <div className="flex items-center space-x-4 text-sm text-gray-500">
                      <span className="bg-gray-100 px-2 py-1 rounded">
                        {source.source}
                      </span>
                      {source.relevance_score && (
                        <div className="flex items-center">
                          <Star className="h-4 w-4 mr-1" />
                          {(source.relevance_score * 100).toFixed(0)}% relevant
                        </div>
                      )}
                    </div>
                  </div>
                  {source.url && (
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-4 p-2 text-gray-400 hover:text-primary-600 transition-colors"
                    >
                      <ExternalLink className="h-5 w-5" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Session Info */}
      {results.session_id && (
        <div className="text-center text-sm text-gray-500">
          Session ID: {results.session_id}
        </div>
      )}
    </div>
  );
};

export default SearchResults;
