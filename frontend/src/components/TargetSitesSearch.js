import React, { useState, useEffect } from 'react';
import { Search, Target, Loader2, AlertCircle, ExternalLink, Star, MapPin, Filter, SortAsc } from 'lucide-react';
import { siteSpecificSearchAPI, getActiveSitesAPI } from '../services/api';

const TargetSitesSearch = () => {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState([]);
  const [activeSites, setActiveSites] = useState({});
  const [selectedSites, setSelectedSites] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [sortBy, setSortBy] = useState('relevance');
  const [filterBySite, setFilterBySite] = useState('');
  const [error, setError] = useState(null);
  const [searchTime, setSearchTime] = useState(0);

  const perPage = 10;

  // Load active sites on component mount
  useEffect(() => {
    loadActiveSites();
  }, []);

  const loadActiveSites = async () => {
    try {
      const response = await getActiveSitesAPI();
      // Convert array of sites to object keyed by site_key
      const sitesObject = {};
      response.active_sites.forEach(site => {
        sitesObject[site.site_key] = site;
      });
      setActiveSites(sitesObject);
      setSelectedSites(Object.keys(sitesObject)); // Select all sites by default
    } catch (error) {
      console.error('Failed to load active sites:', error);
      setError('Failed to load available sites');
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    if (selectedSites.length === 0) {
      setError('Please select at least one site to search');
      return;
    }

    setIsSearching(true);
    setError(null);
    setCurrentPage(1);

    try {
      const startTime = Date.now();
      const response = await siteSpecificSearchAPI({
        query: query.trim(),
        targetSites: selectedSites,
        page: 1,
        perPage,
        sortBy,
        filterBySite: filterBySite || null
      });

      setResults(response.results);
      setPagination(response.pagination);
      setSearchTime((Date.now() - startTime) / 1000);
    } catch (error) {
      console.error('Search failed:', error);
      setError(error.response?.data?.detail || 'Search failed. Please try again.');
    } finally {
      setIsSearching(false);
    }
  };

  const handlePageChange = async (page) => {
    if (page === currentPage || isSearching) return;

    setIsSearching(true);
    try {
      const response = await siteSpecificSearchAPI({
        query: query.trim(),
        targetSites: selectedSites,
        page,
        perPage,
        sortBy,
        filterBySite: filterBySite || null
      });

      setResults(response.results);
      setPagination(response.pagination);
      setCurrentPage(page);
    } catch (error) {
      console.error('Page change failed:', error);
      setError('Failed to load page. Please try again.');
    } finally {
      setIsSearching(false);
    }
  };

  const handleSiteToggle = (siteKey) => {
    setSelectedSites(prev => 
      prev.includes(siteKey) 
        ? prev.filter(s => s !== siteKey)
        : [...prev, siteKey]
    );
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !isSearching) {
      handleSearch();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center space-x-3 mb-4">
            <div className="w-12 h-12 bg-gradient-to-br from-red-500 to-red-600 rounded-full flex items-center justify-center">
              <Target className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-gray-900">Target Sites Search</h1>
          </div>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Search Japanese e-commerce sites for detailed product information with images, prices, and ratings
          </p>
        </div>

        {/* Search Form */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          {/* Query Input */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Search Query
            </label>
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Enter Japanese keywords (e.g., ケーキ, パン, グルメ)"
                  className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500"
                  disabled={isSearching}
                />
              </div>
              <button
                onClick={handleSearch}
                disabled={isSearching || !query.trim() || selectedSites.length === 0}
                className="px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
              >
                {isSearching ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Searching...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-5 h-5" />
                    <span>Search</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Site Selection */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Target Sites ({selectedSites.length} selected)
            </label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(activeSites).map(([siteKey, siteConfig]) => (
                <label key={siteKey} className="flex items-center space-x-3 p-3 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedSites.includes(siteKey)}
                    onChange={() => handleSiteToggle(siteKey)}
                    className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500"
                  />
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">{siteConfig.site_name}</div>
                    <div className="text-sm text-gray-500">{siteConfig.description}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Search Options */}
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center space-x-2">
              <SortAsc className="w-4 h-4 text-gray-500" />
              <label className="text-sm text-gray-700">Sort by:</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-1 border border-gray-300 rounded text-sm focus:ring-red-500 focus:border-red-500"
              >
                <option value="relevance">Relevance</option>
                <option value="title">Title</option>
                <option value="site">Site</option>
                <option value="price">Price</option>
                <option value="rating">Rating</option>
              </select>
            </div>
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-gray-500" />
              <label className="text-sm text-gray-700">Filter by site:</label>
              <select
                value={filterBySite}
                onChange={(e) => setFilterBySite(e.target.value)}
                className="px-3 py-1 border border-gray-300 rounded text-sm focus:ring-red-500 focus:border-red-500"
              >
                <option value="">All Sites</option>
                {Object.entries(activeSites).map(([siteKey, siteConfig]) => (
                  <option key={siteKey} value={siteKey}>{siteConfig.site_name}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-5 h-5 text-red-600" />
              <span className="text-red-800">{error}</span>
            </div>
          </div>
        )}

        {/* Results Header */}
        {pagination && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-600">
                Found <span className="font-medium">{pagination.total_results}</span> results 
                {searchTime > 0 && <span> in {searchTime.toFixed(2)}s</span>}
              </div>
              <div className="text-sm text-gray-600">
                Page {pagination.current_page} of {pagination.total_pages}
              </div>
            </div>
          </div>
        )}

        {/* Loading State */}
        {isSearching && (
          <div className="text-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-red-600 mx-auto mb-4" />
            <p className="text-gray-600">Searching target sites...</p>
          </div>
        )}

        {/* Results Display */}
        {results.length > 0 && (
          <div className="space-y-4 mb-8">
            {results.map((product, index) => (
              <div key={index} className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
                <div className="flex gap-6">
                  {/* Product Image */}
                  <div className="flex-shrink-0">
                    {product.image_url ? (
                      <img
                        src={product.image_url}
                        alt={product.title}
                        className="w-24 h-24 object-cover rounded-lg border border-gray-200"
                        onError={(e) => {
                          e.target.style.display = 'none';
                        }}
                      />
                    ) : (
                      <div className="w-24 h-24 bg-gray-100 rounded-lg border border-gray-200 flex items-center justify-center">
                        <Target className="w-8 h-8 text-gray-400" />
                      </div>
                    )}
                  </div>

                  {/* Product Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="text-lg font-semibold text-gray-900 line-clamp-2">
                        {product.title}
                      </h3>
                      {product.relevance_score && (
                        <div className="flex-shrink-0 ml-4">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {Math.round(product.relevance_score * 100)}% match
                          </span>
                        </div>
                      )}
                    </div>

                    {product.description && (
                      <p className="text-gray-600 text-sm mb-3 line-clamp-2">
                        {product.description}
                      </p>
                    )}

                    {/* Product Metadata */}
                    <div className="flex flex-wrap items-center gap-4 mb-3">
                      <div className="flex items-center space-x-1">
                        <MapPin className="w-4 h-4 text-gray-400" />
                        <span className="text-sm font-medium text-gray-700">{product.site_name}</span>
                      </div>

                      {product.price && (
                        <div className="flex items-center space-x-1">
                          <span className="text-sm text-gray-500">Price:</span>
                          <span className="text-sm font-medium text-green-600">{product.price}</span>
                        </div>
                      )}

                      {product.rating && (
                        <div className="flex items-center space-x-1">
                          <Star className="w-4 h-4 text-yellow-400 fill-current" />
                          <span className="text-sm font-medium text-gray-700">{product.rating}/5</span>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center space-x-3">
                      <a
                        href={product.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center space-x-1 px-3 py-1.5 bg-red-600 text-white text-sm rounded-md hover:bg-red-700 transition-colors"
                      >
                        <ExternalLink className="w-4 h-4" />
                        <span>View Product</span>
                      </a>
                      <button className="inline-flex items-center space-x-1 px-3 py-1.5 border border-gray-300 text-gray-700 text-sm rounded-md hover:bg-gray-50 transition-colors">
                        <span>Save</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {pagination && pagination.total_pages > 1 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={!pagination.has_prev || isSearching}
                  className="px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>

                <div className="flex items-center space-x-1">
                  {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                    let pageNum;
                    if (pagination.total_pages <= 5) {
                      pageNum = i + 1;
                    } else if (currentPage <= 3) {
                      pageNum = i + 1;
                    } else if (currentPage >= pagination.total_pages - 2) {
                      pageNum = pagination.total_pages - 4 + i;
                    } else {
                      pageNum = currentPage - 2 + i;
                    }

                    return (
                      <button
                        key={pageNum}
                        onClick={() => handlePageChange(pageNum)}
                        disabled={isSearching}
                        className={`px-3 py-2 text-sm font-medium rounded-md ${
                          pageNum === currentPage
                            ? 'bg-red-600 text-white'
                            : 'border border-gray-300 text-gray-700 hover:bg-gray-50'
                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                </div>

                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={!pagination.has_next || isSearching}
                  className="px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>

              <div className="text-sm text-gray-600">
                Showing {((currentPage - 1) * perPage) + 1} to {Math.min(currentPage * perPage, pagination.total_results)} of {pagination.total_results} results
              </div>
            </div>
          </div>
        )}

        {/* No Results */}
        {!isSearching && results.length === 0 && query && (
          <div className="text-center py-12">
            <Target className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No products found</h3>
            <p className="text-gray-600">Try adjusting your search query or selecting different sites.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default TargetSitesSearch;
