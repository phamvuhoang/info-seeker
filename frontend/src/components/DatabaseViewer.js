import React, { useState, useEffect } from 'react';
import DatabaseService from '../services/database';
import TableList from './TableList';
import TableViewer from './TableViewer';

const DatabaseViewer = () => {
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadTables();
  }, []);

  const loadTables = async () => {
    try {
      setLoading(true);
      setError(null);
      const tablesData = await DatabaseService.getTables();
      setTables(tablesData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTableSelect = (table) => {
    setSelectedTable(table);
  };

  const handleBackToTables = () => {
    setSelectedTable(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading database tables...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            <strong className="font-bold">Error: </strong>
            <span className="block sm:inline">{error}</span>
          </div>
          <button
            onClick={loadTables}
            className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Database Viewer</h1>
          <p className="text-gray-600">
            Explore and view data from InfoSeeker database tables
          </p>
        </div>

        {selectedTable ? (
          <TableViewer 
            table={selectedTable} 
            onBack={handleBackToTables}
          />
        ) : (
          <TableList 
            tables={tables} 
            onTableSelect={handleTableSelect}
          />
        )}
      </div>
    </div>
  );
};

export default DatabaseViewer;
