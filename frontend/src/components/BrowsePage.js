import React, { useState, useEffect } from 'react';
import SearchBar from './SearchBar';
import ResultsList from './ResultsList';
import { searchHotels, searchRestaurants, getStatistics, triggerManualScraping } from '../services/api';

const BrowsePage = () => {
  const [activeTab, setActiveTab] = useState('hotels');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [scrapingLoading, setScrapingLoading] = useState(false);
  const [scrapingMessage, setScrapingMessage] = useState(null);
  const [pagination, setPagination] = useState({
    page: 1,
    size: 20,
    total: 0,
    totalPages: 0,
    hasNext: false,
    hasPrev: false
  });
  const [filters, setFilters] = useState({
    search: '',
    minRating: null,
    maxRating: null,
    city: '',
    sourceNames: '',
    cuisineType: '', // for restaurants
    minPrice: null, // for hotels
    maxPrice: null  // for hotels
  });

  // Load statistics on component mount
  useEffect(() => {
    loadStatistics();
  }, []);

  // Load data when tab or filters change
  useEffect(() => {
    loadData();
  }, [activeTab, filters, pagination.page]);

  const loadStatistics = async () => {
    try {
      const stats = await getStatistics();
      setStatistics(stats);
    } catch (error) {
      console.error('Error loading statistics:', error);
    }
  };

  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const searchParams = {
        ...filters,
        page: pagination.page,
        size: pagination.size
      };

      let response;
      if (activeTab === 'hotels') {
        response = await searchHotels(searchParams);
      } else {
        response = await searchRestaurants(searchParams);
      }

      setResults(response.items);
      setPagination({
        page: response.page,
        size: response.size,
        total: response.total,
        totalPages: response.total_pages,
        hasNext: response.has_next,
        hasPrev: response.has_prev
      });
    } catch (error) {
      console.error('Error loading data:', error);
      setError('Failed to load data. Please try again.');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (newFilters) => {
    setFilters(newFilters);
    setPagination(prev => ({ ...prev, page: 1 })); // Reset to first page
  };

  const handlePageChange = (newPage) => {
    setPagination(prev => ({ ...prev, page: newPage }));
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setResults([]);
    setPagination(prev => ({ ...prev, page: 1 }));
    // Reset filters that don't apply to the new tab
    if (tab === 'hotels') {
      setFilters(prev => ({ ...prev, cuisineType: '' }));
    } else {
      setFilters(prev => ({ ...prev, minPrice: null, maxPrice: null }));
    }
  };

  const handleManualScraping = async (sourceName) => {
    setScrapingLoading(true);
    setScrapingMessage(null);
    setError(null);

    try {
      const result = await triggerManualScraping(sourceName);

      if (result.status === 'completed') {
        setScrapingMessage(`✅ Successfully scraped ${result.items_scraped} items from ${sourceName}`);
        // Refresh data and statistics
        await loadStatistics();
        await loadData();
      } else if (result.status === 'failed') {
        setScrapingMessage(`❌ Scraping failed for ${sourceName}: ${result.errors?.join(', ') || 'Unknown error'}`);
      } else {
        setScrapingMessage(`⏳ Scraping started for ${sourceName}. Status: ${result.status}`);
      }
    } catch (error) {
      console.error('Error triggering manual scraping:', error);
      setScrapingMessage(`❌ Failed to trigger scraping for ${sourceName}: ${error.message}`);
    } finally {
      setScrapingLoading(false);
      // Clear message after 10 seconds
      setTimeout(() => setScrapingMessage(null), 10000);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Browse Curated Content
          </h1>
          <p className="text-gray-600">
            Discover hotels and restaurants from trusted sources, updated regularly
          </p>
        </div>

        {/* Statistics */}
        {statistics && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-2xl font-bold text-blue-600">
                {statistics.hotels.total.toLocaleString()}
              </div>
              <div className="text-sm text-gray-600">Hotels</div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-2xl font-bold text-green-600">
                {statistics.restaurants.total.toLocaleString()}
              </div>
              <div className="text-sm text-gray-600">Restaurants</div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-2xl font-bold text-purple-600">
                {statistics.hotels.cities + statistics.restaurants.cities}
              </div>
              <div className="text-sm text-gray-600">Cities</div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-2xl font-bold text-orange-600">
                {statistics.hotels.sources + statistics.restaurants.sources}
              </div>
              <div className="text-sm text-gray-600">Sources</div>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="border-b border-gray-200 mb-6">
          <div className="flex justify-between items-center">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => handleTabChange('hotels')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'hotels'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Hotels ({statistics?.hotels.total || 0})
              </button>
              <button
                onClick={() => handleTabChange('restaurants')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'restaurants'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Restaurants ({statistics?.restaurants.total || 0})
              </button>
            </nav>

            {/* Manual Scraping Buttons */}
            <div className="flex space-x-2">
              <button
                onClick={() => handleManualScraping('agoda')}
                disabled={scrapingLoading}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                  scrapingLoading
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                }`}
              >
                {scrapingLoading ? '⏳' : '🔄'} Scrape Hotels
              </button>
              <button
                onClick={() => handleManualScraping('tabelog')}
                disabled={scrapingLoading}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                  scrapingLoading
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-green-100 text-green-700 hover:bg-green-200'
                }`}
              >
                {scrapingLoading ? '⏳' : '🔄'} Scrape Restaurants
              </button>
            </div>
          </div>
        </div>

        {/* Scraping Status Message */}
        {scrapingMessage && (
          <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-6">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-blue-800">{scrapingMessage}</p>
              </div>
            </div>
          </div>
        )}

        {/* Search Bar */}
        <SearchBar
          onSearch={handleSearch}
          filters={filters}
          contentType={activeTab}
        />

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        <ResultsList
          results={results}
          loading={loading}
          contentType={activeTab}
          pagination={pagination}
          onPageChange={handlePageChange}
        />
      </div>
    </div>
  );
};

export default BrowsePage;
