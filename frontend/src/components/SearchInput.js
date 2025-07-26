import React, { useState, useEffect } from 'react';
import { Search, Loader2 } from 'lucide-react';

const SearchInput = ({ onSearch, loading, initialQuery = '' }) => {
  const [query, setQuery] = useState(initialQuery);

  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim() && !loading) {
      onSearch(query.trim());
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          {loading ? (
            <Loader2 className="h-5 w-5 text-gray-400 animate-spin" />
          ) : (
            <Search className="h-5 w-5 text-gray-400" />
          )}
        </div>
        
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask me anything... (e.g., 'What are the latest AI developments?')"
          disabled={loading}
          className="block w-full pl-10 pr-12 py-4 text-lg border border-gray-300 rounded-lg 
                     focus:ring-2 focus:ring-primary-500 focus:border-primary-500 
                     disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed
                     shadow-sm transition-all duration-200"
        />
        
        <div className="absolute inset-y-0 right-0 flex items-center">
          <button
            type="submit"
            disabled={!query.trim() || loading}
            className="mr-3 px-4 py-2 bg-primary-600 text-white rounded-md 
                       hover:bg-primary-700 focus:outline-none focus:ring-2 
                       focus:ring-primary-500 focus:ring-offset-2 
                       disabled:bg-gray-300 disabled:cursor-not-allowed
                       transition-colors duration-200"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </div>
      
      {/* Example queries */}
      <div className="mt-4 flex flex-wrap gap-2">
        <span className="text-sm text-gray-500">Try:</span>
        {[
          'Latest AI developments',
          'Climate change solutions',
          'Python programming best practices',
          'Quantum computing explained'
        ].map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => setQuery(example)}
            disabled={loading}
            className="text-sm text-primary-600 hover:text-primary-800 
                       hover:underline disabled:text-gray-400 disabled:cursor-not-allowed"
          >
            "{example}"
          </button>
        ))}
      </div>
    </form>
  );
};

export default SearchInput;
