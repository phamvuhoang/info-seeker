import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Search, Brain, Database, MapPin } from 'lucide-react';

const Header = () => {
  const location = useLocation();

  const isActive = (path) => {
    return location.pathname === path;
  };

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <Link to="/" className="flex-shrink-0 flex items-center">
              <Brain className="h-8 w-8 text-blue-600" />
              <span className="ml-2 text-xl font-bold text-gray-900">
                InfoSeeker
              </span>
            </Link>
          </div>

          <div className="flex items-center space-x-6">
            <nav className="flex space-x-4">
              <Link
                to="/"
                className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive('/') || isActive('/hybrid')
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Search className="h-4 w-4 mr-2" />
                Search
              </Link>
              <Link
                to="/browse"
                className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive('/browse')
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <MapPin className="h-4 w-4 mr-2" />
                Browse
              </Link>
              <Link
                to="/database"
                className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive('/database')
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Database className="h-4 w-4 mr-2" />
                Database
              </Link>
            </nav>
            <span className="text-sm text-gray-500">
              AI-Powered Search Platform
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
