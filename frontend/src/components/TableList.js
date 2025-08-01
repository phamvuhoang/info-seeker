import React from 'react';

const TableList = ({ tables, onTableSelect }) => {
  const formatNumber = (num) => {
    return new Intl.NumberFormat().format(num);
  };

  const getTableIcon = (tableName) => {
    const icons = {
      'infoseeker_documents': '📄',
      'user_sessions': '👤',
      'source_scores': '⭐',
      'agent_workflow_sessions': '🤖',
      'agent_execution_logs': '📋',
      'source_reliability': '🔍',
      'search_feedback': '💬',
      'search_history': '🕒'
    };
    return icons[tableName] || '📊';
  };

  const getRowCountColor = (count) => {
    if (count === 0) return 'text-gray-500';
    if (count < 100) return 'text-green-600';
    if (count < 1000) return 'text-blue-600';
    return 'text-purple-600';
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {tables.map((table) => (
        <div
          key={table.table_name}
          className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-200 cursor-pointer border border-gray-200"
          onClick={() => onTableSelect(table)}
        >
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <span className="text-2xl mr-3">{getTableIcon(table.table_name)}</span>
                <h3 className="text-lg font-semibold text-gray-900 truncate">
                  {table.table_name}
                </h3>
              </div>
              <div className="text-right">
                <div className={`text-2xl font-bold ${getRowCountColor(table.row_count)}`}>
                  {formatNumber(table.row_count)}
                </div>
                <div className="text-xs text-gray-500">rows</div>
              </div>
            </div>

            <p className="text-gray-600 text-sm mb-4 line-clamp-2">
              {table.description}
            </p>

            <div className="border-t pt-4">
              <div className="flex items-center justify-between text-sm text-gray-500">
                <span>{table.columns.length} columns</span>
                <span className="text-blue-600 hover:text-blue-800">
                  View Data →
                </span>
              </div>
            </div>

            {/* Column preview */}
            <div className="mt-3">
              <div className="text-xs text-gray-400 mb-1">Columns:</div>
              <div className="flex flex-wrap gap-1">
                {table.columns.slice(0, 4).map((col, index) => (
                  <span
                    key={index}
                    className="inline-block bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded"
                  >
                    {col.name}
                  </span>
                ))}
                {table.columns.length > 4 && (
                  <span className="inline-block text-gray-400 text-xs px-2 py-1">
                    +{table.columns.length - 4} more
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default TableList;
