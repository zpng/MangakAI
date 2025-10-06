/**
 * WebSocket service for real-time communication with MangakAI backend
 */

class WebSocketService {
  constructor() {
    this.ws = null;
    this.sessionId = this.getOrCreateSessionId();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.listeners = new Map();
    this.isConnected = false;
    this.connectionPromise = null;
  }

  /**
   * Get or create session ID
   */
  getOrCreateSessionId() {
    let sessionId = localStorage.getItem('mangakai_session_id');
    if (!sessionId) {
      sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('mangakai_session_id', sessionId);
    }
    return sessionId;
  }

  /**
   * Connect to WebSocket server
   */
  async connect() {
    if (this.connectionPromise) {
      return this.connectionPromise;
    }

    this.connectionPromise = new Promise((resolve, reject) => {
      try {
        const wsUrl = `ws://localhost:8000/ws/${this.sessionId}`;
        console.log('Connecting to WebSocket:', wsUrl);
        
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.emit('connected');
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket disconnected:', event.code, event.reason);
          this.isConnected = false;
          this.connectionPromise = null;
          this.emit('disconnected');
          
          // Attempt reconnection if not a normal closure
          if (event.code !== 1000) {
            this.attemptReconnect();
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.emit('error', error);
          reject(error);
        };

        // Connection timeout
        setTimeout(() => {
          if (!this.isConnected) {
            reject(new Error('WebSocket connection timeout'));
          }
        }, 10000);

      } catch (error) {
        console.error('Failed to create WebSocket connection:', error);
        reject(error);
      }
    });

    return this.connectionPromise;
  }

  /**
   * Handle incoming WebSocket messages
   */
  handleMessage(data) {
    const { type } = data;

    switch (type) {
      case 'progress_update':
        this.emit('progress_update', data.data);
        break;
      
      case 'connection_established':
        console.log('Connection established for session:', data.session_id);
        break;
      
      case 'heartbeat':
        // Respond to heartbeat
        this.send({ type: 'pong', timestamp: data.timestamp });
        break;
      
      case 'pong':
        // Handle pong response
        break;
      
      case 'subscribed':
        console.log('Subscribed to task:', data.task_id);
        this.emit('subscribed', data);
        break;
      
      case 'unsubscribed':
        console.log('Unsubscribed from task:', data.task_id);
        this.emit('unsubscribed', data);
        break;
      
      case 'error':
        console.error('WebSocket server error:', data.message);
        this.emit('server_error', data);
        break;
      
      default:
        console.log('Unknown message type:', type, data);
        this.emit('message', data);
    }
  }

  /**
   * Send message to server
   */
  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    } else {
      console.warn('WebSocket not connected, cannot send message:', data);
      return false;
    }
  }

  /**
   * Subscribe to task updates
   */
  subscribeToTask(taskId) {
    return this.send({
      type: 'subscribe_task',
      task_id: taskId
    });
  }

  /**
   * Unsubscribe from task updates
   */
  unsubscribeFromTask(taskId) {
    return this.send({
      type: 'unsubscribe_task',
      task_id: taskId
    });
  }

  /**
   * Send ping to server
   */
  ping() {
    return this.send({
      type: 'ping',
      timestamp: Date.now()
    });
  }

  /**
   * Get connection info
   */
  getConnectionInfo() {
    return this.send({
      type: 'get_connection_info'
    });
  }

  /**
   * Attempt to reconnect
   */
  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${delay}ms`);
      
      setTimeout(() => {
        this.connect().catch(error => {
          console.error('Reconnection failed:', error);
        });
      }, delay);
    } else {
      console.error('Max reconnection attempts reached');
      this.emit('max_reconnect_attempts_reached');
    }
  }

  /**
   * Add event listener
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  /**
   * Remove event listener
   */
  off(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  /**
   * Emit event to listeners
   */
  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Error in event listener:', error);
        }
      });
    }
  }

  /**
   * Disconnect WebSocket
   */
  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.isConnected = false;
    this.connectionPromise = null;
  }

  /**
   * Get connection status
   */
  getConnectionStatus() {
    return {
      isConnected: this.isConnected,
      sessionId: this.sessionId,
      reconnectAttempts: this.reconnectAttempts
    };
  }
}

// Create and export singleton instance
const websocketService = new WebSocketService();
export default websocketService;