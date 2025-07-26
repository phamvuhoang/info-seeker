import React, { useState } from 'react';
import SearchInput from './SearchInput';
import SearchResults from './SearchResults';
import { searchAPI } from '../services/api';

const SearchPage = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(null);

  const handleSearch = async (searchQuery) => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setError(null);
    setQuery(searchQuery);

    try {
      const response = await searchAPI(searchQuery, sessionId);
      setResults(response);
      if (response.session_id) {
        setSessionId(response.session_id);
      }
    } catch (err) {
      setError(err.message || 'An error occurred while searching');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Hero Section */}
      {!results && (
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Welcome to InfoSeeker
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            AI-powered search for junk-free, personalized information retrieval
          </p>
        </div>
      )}

      {/* Search Input */}
      <div className="mb-8">
        <SearchInput 
          onSearch={handleSearch} 
          loading={loading}
          initialQuery={query}
        />
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {/* Search Results */}
      {results && (
        <SearchResults 
          results={results} 
          loading={loading}
          query={query}
        />
      )}

      {/* Features Section (shown when no results) */}
      {!results && !loading && (
        <div className="mt-16">
          <h2 className="text-2xl font-bold text-gray-900 mb-8 text-center">
            Key Features
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="bg-primary-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🔍</span>
              </div>
              <h3 className="text-lg font-semibold mb-2">Web Search Automation</h3>
              <p className="text-gray-600">
                Real-time web searches with browser automation for accurate, up-to-date information
              </p>
            </div>
            <div className="text-center">
              <div className="bg-primary-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🧠</span>
              </div>
              <h3 className="text-lg font-semibold mb-2">AI Answer Generation</h3>
              <p className="text-gray-600">
                Context-aware answers using advanced AI with Retrieval-Augmented Generation
              </p>
            </div>
            <div className="text-center">
              <div className="bg-primary-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">📚</span>
              </div>
              <h3 className="text-lg font-semibold mb-2">Stored Data Search</h3>
              <p className="text-gray-600">
                Semantic search through stored content using vector embeddings for efficient retrieval
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchPage;
