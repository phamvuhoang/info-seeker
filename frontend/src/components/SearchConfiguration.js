import React, { useState, useEffect } from 'react';
import { Settings, Globe, Database, Target, Brain, Info, ChevronDown, ChevronUp } from 'lucide-react';
import { getActiveSitesAPI, analyzeSearchIntentAPI } from '../services/api';

const SearchConfiguration = ({ 
  searchConfig, 
  onConfigChange, 
  query,
  isSearching,
  className = "" 
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeSites, setActiveSites] = useState([]);
  const [intentAnalysis, setIntentAnalysis] = useState(null);
  const [loadingIntent, setLoadingIntent] = useState(false);
  const [loadingSites, setLoadingSites] = useState(false);

  // Load active sites on component mount
  useEffect(() => {
    loadActiveSites();
  }, []);

  // Analyze intent when query changes
  useEffect(() => {
    if (query && query.trim().length > 2) {
      analyzeIntent(query);
    } else {
      setIntentAnalysis(null);
    }
  }, [query]);

  const loadActiveSites = async () => {
    try {
      setLoadingSites(true);
      const response = await getActiveSitesAPI();
      setActiveSites(response.active_sites || []);
    } catch (error) {
      console.error('Failed to load active sites:', error);
    } finally {
      setLoadingSites(false);
    }
  };

  const analyzeIntent = async (queryText) => {
    try {
      setLoadingIntent(true);
      const analysis = await analyzeSearchIntentAPI(queryText);
      setIntentAnalysis(analysis);
      
      // Auto-configure based on intent if intelligent search is enabled
      if (searchConfig.useIntelligentSearch && analysis.recommendations) {
        const newConfig = {
          ...searchConfig,
          includeSiteSpecific: analysis.recommendations.use_site_specific,
          targetSites: analysis.recommendations.target_sites || []
        };
        onConfigChange(newConfig);
      }
    } catch (error) {
      console.error('Failed to analyze search intent:', error);
      setIntentAnalysis(null);
    } finally {
      setLoadingIntent(false);
    }
  };

  const handleConfigChange = (key, value) => {
    const newConfig = { ...searchConfig, [key]: value };
    onConfigChange(newConfig);
  };

  const handleSiteToggle = (siteKey) => {
    const currentSites = searchConfig.targetSites || [];
    const newSites = currentSites.includes(siteKey)
      ? currentSites.filter(s => s !== siteKey)
      : [...currentSites, siteKey];
    
    handleConfigChange('targetSites', newSites);
    
    // Auto-enable site-specific search if sites are selected
    if (newSites.length > 0 && !searchConfig.includeSiteSpecific) {
      handleConfigChange('includeSiteSpecific', true);
    }
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getSiteIcon = (category) => {
    switch (category) {
      case 'food_ordering':
        return '🍱';
      case 'bread_products':
        return '🍞';
      case 'premium_food':
        return '🍽️';
      default:
        return '🌐';
    }
  };

  return (
    <div className={`bg-white border border-gray-200 rounded-lg shadow-sm ${className}`}>
      {/* Header */}
      <div 
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center space-x-2">
          <Settings className="w-5 h-5 text-gray-600" />
          <span className="font-medium text-gray-900">Search Configuration</span>
          {intentAnalysis && (
            <span className={`text-sm px-2 py-1 rounded-full bg-gray-100 ${getConfidenceColor(intentAnalysis.confidence)}`}>
              {Math.round(intentAnalysis.confidence * 100)}% confidence
            </span>
          )}
        </div>
        {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-gray-200 p-4 space-y-4">
          
          {/* Intent Analysis */}
          {intentAnalysis && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-center space-x-2 mb-2">
                <Brain className="w-4 h-4 text-blue-600" />
                <span className="font-medium text-blue-900">Search Intent Analysis</span>
                {loadingIntent && <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />}
              </div>
              <div className="text-sm text-blue-800">
                <p><strong>Language:</strong> {intentAnalysis.detected_language}</p>
                <p><strong>Category:</strong> {intentAnalysis.category}</p>
                <p><strong>Reasoning:</strong> {intentAnalysis.reasoning}</p>
              </div>
            </div>
          )}

          {/* Search Type Configuration */}
          <div className="space-y-3">
            <h4 className="font-medium text-gray-900">Search Types</h4>
            
            {/* Intelligent Search Toggle */}
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={searchConfig.useIntelligentSearch}
                onChange={(e) => handleConfigChange('useIntelligentSearch', e.target.checked)}
                disabled={isSearching}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <div className="flex items-center space-x-2">
                <Brain className="w-4 h-4 text-purple-600" />
                <span className="text-sm font-medium">Intelligent Search</span>
                <Info className="w-3 h-3 text-gray-400" title="Automatically detects optimal search strategy" />
              </div>
            </label>

            {/* Manual Configuration (only when intelligent search is off) */}
            {!searchConfig.useIntelligentSearch && (
              <div className="ml-6 space-y-2 border-l-2 border-gray-200 pl-4">
                <label className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    checked={searchConfig.includeRag}
                    onChange={(e) => handleConfigChange('includeRag', e.target.checked)}
                    disabled={isSearching}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <div className="flex items-center space-x-2">
                    <Database className="w-4 h-4 text-green-600" />
                    <span className="text-sm">Knowledge Base Search</span>
                  </div>
                </label>

                <label className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    checked={searchConfig.includeWeb}
                    onChange={(e) => handleConfigChange('includeWeb', e.target.checked)}
                    disabled={isSearching}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <div className="flex items-center space-x-2">
                    <Globe className="w-4 h-4 text-blue-600" />
                    <span className="text-sm">General Web Search</span>
                  </div>
                </label>

                <label className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    checked={searchConfig.includeSiteSpecific}
                    onChange={(e) => handleConfigChange('includeSiteSpecific', e.target.checked)}
                    disabled={isSearching}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <div className="flex items-center space-x-2">
                    <Target className="w-4 h-4 text-orange-600" />
                    <span className="text-sm">Site-Specific Search</span>
                  </div>
                </label>
              </div>
            )}
          </div>

          {/* Site Selection (when site-specific search is enabled) */}
          {(searchConfig.includeSiteSpecific || searchConfig.useIntelligentSearch) && (
            <div className="space-y-3">
              <h4 className="font-medium text-gray-900">Target Sites</h4>
              {loadingSites ? (
                <div className="flex items-center space-x-2 text-gray-600">
                  <div className="w-4 h-4 border-2 border-gray-600 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm">Loading sites...</span>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-2">
                  {activeSites.map((site) => (
                    <label key={site.site_key} className="flex items-center space-x-3 p-2 hover:bg-gray-50 rounded">
                      <input
                        type="checkbox"
                        checked={(searchConfig.targetSites || []).includes(site.site_key)}
                        onChange={() => handleSiteToggle(site.site_key)}
                        disabled={isSearching || searchConfig.useIntelligentSearch}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <div className="flex items-center space-x-2 flex-1">
                        <span className="text-lg">{getSiteIcon(site.category)}</span>
                        <div className="flex-1">
                          <div className="text-sm font-medium">{site.site_name}</div>
                          <div className="text-xs text-gray-500">{site.site_key}</div>
                        </div>
                        <span className="text-xs bg-gray-100 px-2 py-1 rounded">{site.category}</span>
                      </div>
                    </label>
                  ))}
                </div>
              )}
              
              {searchConfig.useIntelligentSearch && (
                <div className="text-xs text-gray-500 italic">
                  Sites are automatically selected based on query analysis
                </div>
              )}
            </div>
          )}

          {/* Max Results */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-900">
              Maximum Results: {searchConfig.maxResults}
            </label>
            <input
              type="range"
              min="5"
              max="20"
              value={searchConfig.maxResults}
              onChange={(e) => handleConfigChange('maxResults', parseInt(e.target.value))}
              disabled={isSearching}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-500">
              <span>5</span>
              <span>20</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchConfiguration;
