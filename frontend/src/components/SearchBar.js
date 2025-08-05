import React, { useState, useEffect } from 'react';

const SearchBar = ({ onSearch, filters, contentType }) => {
  const [localFilters, setLocalFilters] = useState(filters);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Update local filters when props change
  useEffect(() => {
    setLocalFilters(filters);
  }, [filters]);

  const handleInputChange = (field, value) => {
    setLocalFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch(localFilters);
  };

  const handleReset = () => {
    const resetFilters = {
      search: '',
      minRating: null,
      maxRating: null,
      city: '',
      sourceNames: '',
      cuisineType: '',
      minPrice: null,
      maxPrice: null
    };
    setLocalFilters(resetFilters);
    onSearch(resetFilters);
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6 mb-6">
      <form onSubmit={handleSubmit}>
        {/* Basic Search */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div className="md:col-span-2">
            <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-1">
              Search
            </label>
            <input
              type="text"
              id="search"
              value={localFilters.search}
              onChange={(e) => handleInputChange('search', e.target.value)}
              placeholder={`Search ${contentType} by name or address...`}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label htmlFor="city" className="block text-sm font-medium text-gray-700 mb-1">
              City
            </label>
            <input
              type="text"
              id="city"
              value={localFilters.city}
              onChange={(e) => handleInputChange('city', e.target.value)}
              placeholder="e.g., Tokyo, Osaka"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        {/* Advanced Filters Toggle */}
        <div className="mb-4">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            {showAdvanced ? 'Hide' : 'Show'} Advanced Filters
          </button>
        </div>

        {/* Advanced Filters */}
        {showAdvanced && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4 p-4 bg-gray-50 rounded-md">
            {/* Rating Filters */}
            <div>
              <label htmlFor="minRating" className="block text-sm font-medium text-gray-700 mb-1">
                Min Rating
              </label>
              <select
                id="minRating"
                value={localFilters.minRating || ''}
                onChange={(e) => handleInputChange('minRating', e.target.value ? parseFloat(e.target.value) : null)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Any</option>
                <option value="1">1+ Stars</option>
                <option value="2">2+ Stars</option>
                <option value="3">3+ Stars</option>
                <option value="4">4+ Stars</option>
                <option value="4.5">4.5+ Stars</option>
              </select>
            </div>

            <div>
              <label htmlFor="maxRating" className="block text-sm font-medium text-gray-700 mb-1">
                Max Rating
              </label>
              <select
                id="maxRating"
                value={localFilters.maxRating || ''}
                onChange={(e) => handleInputChange('maxRating', e.target.value ? parseFloat(e.target.value) : null)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Any</option>
                <option value="2">Up to 2 Stars</option>
                <option value="3">Up to 3 Stars</option>
                <option value="4">Up to 4 Stars</option>
                <option value="5">Up to 5 Stars</option>
              </select>
            </div>

            {/* Source Filter */}
            <div>
              <label htmlFor="sourceNames" className="block text-sm font-medium text-gray-700 mb-1">
                Source
              </label>
              <select
                id="sourceNames"
                value={localFilters.sourceNames}
                onChange={(e) => handleInputChange('sourceNames', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All Sources</option>
                {contentType === 'hotels' && <option value="agoda">Agoda</option>}
                {contentType === 'restaurants' && <option value="tabelog">Tabelog</option>}
              </select>
            </div>

            {/* Content-specific filters */}
            {contentType === 'restaurants' && (
              <div>
                <label htmlFor="cuisineType" className="block text-sm font-medium text-gray-700 mb-1">
                  Cuisine Type
                </label>
                <input
                  type="text"
                  id="cuisineType"
                  value={localFilters.cuisineType}
                  onChange={(e) => handleInputChange('cuisineType', e.target.value)}
                  placeholder="e.g., Japanese, Italian"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            )}

            {contentType === 'hotels' && (
              <>
                <div>
                  <label htmlFor="minPrice" className="block text-sm font-medium text-gray-700 mb-1">
                    Min Price
                  </label>
                  <input
                    type="number"
                    id="minPrice"
                    value={localFilters.minPrice || ''}
                    onChange={(e) => handleInputChange('minPrice', e.target.value ? parseFloat(e.target.value) : null)}
                    placeholder="Min price per night"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label htmlFor="maxPrice" className="block text-sm font-medium text-gray-700 mb-1">
                    Max Price
                  </label>
                  <input
                    type="number"
                    id="maxPrice"
                    value={localFilters.maxPrice || ''}
                    onChange={(e) => handleInputChange('maxPrice', e.target.value ? parseFloat(e.target.value) : null)}
                    placeholder="Max price per night"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </>
            )}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            type="submit"
            className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
          >
            Search
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="flex-1 sm:flex-none bg-gray-200 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
          >
            Reset
          </button>
        </div>
      </form>
    </div>
  );
};

export default SearchBar;
