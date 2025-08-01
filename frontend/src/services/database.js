import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class DatabaseService {
  constructor() {
    this.api = axios.create({
      baseURL: `${API_BASE_URL}/api/v1/database`,
      timeout: 30000,
    });
  }

  /**
   * Get list of all database tables
   */
  async getTables() {
    try {
      const response = await this.api.get('/tables');
      return response.data;
    } catch (error) {
      console.error('Error fetching tables:', error);
      throw new Error(error.response?.data?.detail || 'Failed to fetch tables');
    }
  }

  /**
   * Get data from a specific table with pagination
   */
  async getTableData(tableName, options = {}) {
    try {
      const params = {
        page: options.page || 1,
        page_size: options.pageSize || 20,
        ...(options.sortBy && { sort_by: options.sortBy }),
        ...(options.sortOrder && { sort_order: options.sortOrder }),
        ...(options.search && { search: options.search }),
      };

      const response = await this.api.get(`/tables/${tableName}/data`, { params });
      return response.data;
    } catch (error) {
      console.error(`Error fetching data for table ${tableName}:`, error);
      throw new Error(error.response?.data?.detail || `Failed to fetch data for table ${tableName}`);
    }
  }

  /**
   * Delete a row from a table
   */
  async deleteRow(tableName, rowId) {
    try {
      const response = await this.api.delete(`/tables/${tableName}/rows/${rowId}`);
      return response.data;
    } catch (error) {
      console.error(`Error deleting row ${rowId} from table ${tableName}:`, error);
      throw new Error(error.response?.data?.detail || `Failed to delete row from table ${tableName}`);
    }
  }

  /**
   * Update a row in a table
   */
  async updateRow(tableName, rowId, rowData) {
    try {
      const response = await this.api.put(`/tables/${tableName}/rows/${rowId}`, {
        row_data: rowData
      });
      return response.data;
    } catch (error) {
      console.error(`Error updating row ${rowId} in table ${tableName}:`, error);
      throw new Error(error.response?.data?.detail || `Failed to update row in table ${tableName}`);
    }
  }
}

export default new DatabaseService();
