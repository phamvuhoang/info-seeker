import React, { useState } from 'react';
import { Search, Target, FolderOpen, Database, Activity } from 'lucide-react';

const MainNavigation = ({ activeTab, onTabChange }) => {
  const tabs = [
    {
      id: 'search',
      label: 'Search',
      icon: Search,
      description: 'RAG + Web Search'
    },
    {
      id: 'target-sites',
      label: 'Target Sites Search',
      icon: Target,
      description: 'Japanese E-commerce'
    },
    {
      id: 'browse',
      label: 'Browse',
      icon: FolderOpen,
      description: 'Content Browser'
    },
    {
      id: 'database',
      label: 'Database',
      icon: Database,
      description: 'Database Viewer'
    }
  ];

  return (
    <div className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`
                  flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors duration-200
                  ${isActive
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'text-blue-600' : 'text-gray-400'}`} />
                <div className="flex flex-col items-start">
                  <span className="font-medium">{tab.label}</span>
                  <span className="text-xs text-gray-400 hidden sm:block">{tab.description}</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>
      
      {/* Tab indicator for mobile */}
      <div className="sm:hidden">
        <div className="px-4 py-2 bg-gray-50 border-t border-gray-200">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-blue-600" />
            <span className="text-sm text-gray-600">
              {tabs.find(tab => tab.id === activeTab)?.description}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MainNavigation;
