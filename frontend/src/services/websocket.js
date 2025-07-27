export class SearchSSE {
  constructor(sessionId, onProgress, onResult, onError) {
    this.sessionId = sessionId;
    this.onProgress = onProgress;
    this.onResult = onResult;
    this.onError = onError;
    this.eventSource = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // Start with 1 second
  }

  connect() {
    // Use relative SSE URL to go through nginx proxy
    const sseUrl = `/sse/${this.sessionId}`;

    console.log('Attempting SSE connection to:', sseUrl);
    console.log('Session ID:', this.sessionId);

    try {
      this.eventSource = new EventSource(sseUrl);

      this.eventSource.onopen = () => {
        console.log('SSE connected successfully to:', sseUrl);
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
      };

      this.eventSource.onmessage = (event) => {
        try {
          const update = JSON.parse(event.data);

          // Skip heartbeat messages
          if (update.type === 'heartbeat') {
            return;
          }

          if (update.type === 'progress_update') {
            this.onProgress(update);
          } else if (update.type === 'final_result') {
            this.onResult(update);
          } else if (update.type === 'error') {
            this.onError(update.error || 'Unknown error occurred');
          }
        } catch (error) {
          console.error('Error parsing SSE message:', error);
          this.onError('Error parsing server message');
        }
      };

      this.eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        console.error('SSE URL was:', sseUrl);

        // EventSource will automatically reconnect, but we can handle errors
        if (this.eventSource.readyState === EventSource.CLOSED) {
          this.onError('Connection closed');
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          }
        }
      };
    } catch (error) {
      console.error('Failed to create SSE connection:', error);
      this.onError('Failed to establish connection');
    }
  }

  attemptReconnect() {
    this.reconnectAttempts++;
    console.log(`Attempting to reconnect SSE (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

    setTimeout(() => {
      this.connect();
    }, this.reconnectDelay);

    // Exponential backoff
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000); // Max 30 seconds
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  // SSE is one-way communication, no need for sendMessage
}

// Agent progress states
export const AGENT_STATUS = {
  WAITING: 'waiting',
  STARTED: 'started',
  COMPLETED: 'completed',
  FAILED: 'failed'
};

// Progress update types
export const UPDATE_TYPES = {
  PROGRESS_UPDATE: 'progress_update',
  FINAL_RESULT: 'final_result',
  ERROR: 'error'
};

// Default agent list for initialization
export const DEFAULT_AGENTS = [
  { name: 'RAG Specialist', status: AGENT_STATUS.WAITING, message: 'Waiting to start...' },
  { name: 'Web Search Specialist', status: AGENT_STATUS.WAITING, message: 'Waiting to start...' },
  { name: 'Information Synthesizer', status: AGENT_STATUS.WAITING, message: 'Waiting to start...' },
  { name: 'Information Validator', status: AGENT_STATUS.WAITING, message: 'Waiting to start...' },
  { name: 'Answer Generator', status: AGENT_STATUS.WAITING, message: 'Waiting to start...' }
];

// Utility functions
export const getAgentStatusColor = (status) => {
  switch (status) {
    case AGENT_STATUS.COMPLETED:
      return 'bg-green-500';
    case AGENT_STATUS.STARTED:
      return 'bg-blue-500 animate-pulse';
    case AGENT_STATUS.FAILED:
      return 'bg-red-500';
    default:
      return 'bg-gray-300';
  }
};

export const getAgentStatusIcon = (status) => {
  switch (status) {
    case AGENT_STATUS.COMPLETED:
      return '✓';
    case AGENT_STATUS.STARTED:
      return '⟳';
    case AGENT_STATUS.FAILED:
      return '✗';
    default:
      return '○';
  }
};

export const formatTimestamp = (timestamp) => {
  if (!timestamp) return '';
  
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  } catch (error) {
    return '';
  }
};

export const calculateProgress = (agents) => {
  const completedAgents = agents.filter(agent => 
    agent.status === AGENT_STATUS.COMPLETED || agent.status === AGENT_STATUS.FAILED
  ).length;
  
  return Math.round((completedAgents / agents.length) * 100);
};
