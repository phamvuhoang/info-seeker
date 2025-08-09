import React, { useState } from 'react';
import MainNavigation from './MainNavigation';
import RealTimeSearch from './RealTimeSearch';
import TargetSitesSearch from './TargetSitesSearch';
import BrowsePage from './BrowsePage';
import DatabaseViewer from './DatabaseViewer';

const MainApp = () => {
  const [activeTab, setActiveTab] = useState('search');

  const renderActiveTab = () => {
    switch (activeTab) {
      case 'search':
        return <RealTimeSearch />;
      case 'target-sites':
        return <TargetSitesSearch />;
      case 'browse':
        return <BrowsePage />;
      case 'database':
        return <DatabaseViewer />;
      default:
        return <RealTimeSearch />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <MainNavigation 
        activeTab={activeTab} 
        onTabChange={setActiveTab} 
      />
      
      {/* Main Content */}
      <main className="flex-1">
        {renderActiveTab()}
      </main>
    </div>
  );
};

export default MainApp;
