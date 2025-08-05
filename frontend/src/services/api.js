import axios from 'axios';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 60000, // 60 seconds timeout for search requests
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log(`Making ${config.method?.toUpperCase()} request to ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Error:', error);
    
    if (error.response) {
      // Server responded with error status
      const message = error.response.data?.detail || error.response.data?.message || 'Server error';
      throw new Error(message);
    } else if (error.request) {
      // Request was made but no response received
      throw new Error('No response from server. Please check your connection.');
    } else {
      // Something else happened
      throw new Error(error.message || 'An unexpected error occurred');
    }
  }
);

// API functions
export const healthCheck = async () => {
  try {
    const response = await api.get('/health');
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const searchAPI = async (query, sessionId = null) => {
  try {
    const payload = {
      query,
      max_results: 10,
      include_web: true,
      include_stored: true,
    };

    const params = sessionId ? { session_id: sessionId } : {};

    const response = await api.post('/api/v1/search', payload, { params });
    return response.data;
  } catch (error) {
    throw error;
  }
};

// Predefined Content API functions

export const searchHotels = async (filters = {}) => {
  try {
    const params = new URLSearchParams();

    // Add filters to params
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        params.append(key, value);
      }
    });

    const response = await api.get(`/api/v1/predefined_content/hotels?${params.toString()}`);
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const searchRestaurants = async (filters = {}) => {
  try {
    const params = new URLSearchParams();

    // Add filters to params
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        params.append(key, value);
      }
    });

    const response = await api.get(`/api/v1/predefined_content/restaurants?${params.toString()}`);
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const getHotel = async (hotelId) => {
  try {
    const response = await api.get(`/api/v1/predefined_content/hotels/${hotelId}`);
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const getRestaurant = async (restaurantId) => {
  try {
    const response = await api.get(`/api/v1/predefined_content/restaurants/${restaurantId}`);
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const getStatistics = async () => {
  try {
    const response = await api.get('/api/v1/predefined_content/statistics');
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const triggerManualScraping = async (sourceName) => {
  try {
    const response = await api.post(`/api/v1/predefined_content/scrape/${sourceName}`);
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const getScrapingStatus = async () => {
  try {
    const response = await api.get('/api/v1/predefined_content/scraping/status');
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const addCustomSchedule = async (sourceName, cronExpression) => {
  try {
    const params = new URLSearchParams({ cron_expression: cronExpression });
    const response = await api.post(`/api/v1/predefined_content/scraping/schedule/${sourceName}?${params.toString()}`);
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const removeCustomSchedule = async (sourceName) => {
  try {
    const response = await api.delete(`/api/v1/predefined_content/scraping/schedule/${sourceName}`);
    return response.data;
  } catch (error) {
    throw error;
  }
};

export default api;
