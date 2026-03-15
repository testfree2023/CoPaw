/**
 * Task WebSocket client for real-time progress updates
 */

export interface TaskProgressEvent {
  task_id: string;
  event: {
    type: string;
    status?: string;
    response?: string;
    error?: string;
    reason?: string;
    verified?: boolean;
    [key: string]: any;
  };
}

export type ProgressEventHandler = (event: TaskProgressEvent) => void;

/**
 * TaskProgressClient - WebSocket client for task progress streaming
 */
export class TaskProgressClient {
  private ws: WebSocket | null = null;
  private currentTaskId: string | null = null;
  private subscriptions: Map<string, Set<ProgressEventHandler>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || '';
    // Get WebSocket URL from current location if baseUrl not provided
    if (!this.baseUrl) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host || 'localhost:8088';
      this.baseUrl = `${protocol}//${host}`;
    }
  }

  /**
   * Subscribe to task progress updates
   */
  subscribe(taskId: string, handler: ProgressEventHandler): () => void {
    // Check if already subscribed to this task
    const existingHandlers = this.subscriptions.get(taskId);
    if (existingHandlers && existingHandlers.has(handler)) {
      console.log('[TaskWebSocket] Handler already subscribed to task:', taskId);
      return () => {
        this.unsubscribe(taskId, handler);
      };
    }

    // Add handler to subscriptions
    if (!this.subscriptions.has(taskId)) {
      this.subscriptions.set(taskId, new Set());
    }
    this.subscriptions.get(taskId)!.add(handler);

    // Connect if not already connected to this task
    this.connect(taskId);

    // Return unsubscribe function
    return () => {
      this.unsubscribe(taskId, handler);
    };
  }

  /**
   * Unsubscribe from task progress updates
   */
  unsubscribe(taskId: string, handler: ProgressEventHandler): void {
    const handlers = this.subscriptions.get(taskId);
    if (handlers) {
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.subscriptions.delete(taskId);
        // Close connection if no more subscriptions
        if (this.subscriptions.size === 0) {
          this.disconnect();
        }
      }
    }
  }

  /**
   * Connect to WebSocket server
   */
  private connect(taskId: string): void {
    // Check if already connected to the same task
    if (this.ws && this.ws.readyState === WebSocket.OPEN && this.currentTaskId === taskId) {
      console.log('[TaskWebSocket] Already connected to task:', taskId);
      return;
    }

    // Check if connecting to any task
    if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
      console.log('[TaskWebSocket] Already connecting, will subscribe when ready:', taskId);
      return;
    }

    // Close existing connection if switching to a different task
    if (this.ws) {
      this.ws.onclose = null; // Prevent reconnect
      this.ws.close();
      this.ws = null;
    }

    this.currentTaskId = taskId;
    const wsUrl = `${this.baseUrl}/api/task-ws/${taskId}`;
    console.log('[TaskWebSocket] Connecting to:', wsUrl);

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('[TaskWebSocket] Connected');
      this.reconnectAttempts = 0;
      this.startPingInterval();

      // Subscribe to all pending tasks
      this.subscriptions.forEach((_, id) => {
        this.subscribeToTask(id);
      });
    };

    this.ws.onmessage = (event) => {
      try {
        const data: TaskProgressEvent = JSON.parse(event.data);
        console.log('[TaskWebSocket] Received:', data);
        this.handleEvent(data);
      } catch (error) {
        console.error('[TaskWebSocket] Failed to parse message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('[TaskWebSocket] Error:', error);
    };

    this.ws.onclose = () => {
      console.log('[TaskWebSocket] Disconnected');
      this.stopPingInterval();
      this.attemptReconnect();
    };
  }

  /**
   * Subscribe to a specific task
   */
  private subscribeToTask(taskId: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      // The subscription happens automatically on connection
      console.log('[TaskWebSocket] Subscribed to task:', taskId);
    }
  }

  /**
   * Handle incoming event
   */
  private handleEvent(data: TaskProgressEvent): void {
    const handlers = this.subscriptions.get(data.task_id);
    if (handlers) {
      handlers.forEach(handler => handler(data));
    }
  }

  /**
   * Attempt to reconnect after disconnection
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts && this.subscriptions.size > 0) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      console.log(`[TaskWebSocket] Attempting reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
      setTimeout(() => {
        // Reconnect to first subscribed task
        const firstTaskId = Array.from(this.subscriptions.keys())[0];
        if (firstTaskId) {
          this.connect(firstTaskId);
        }
      }, delay);
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.stopPingInterval();
    }
  }

  /**
   * Start ping interval to keep connection alive
   */
  private startPingInterval(): void {
    this.stopPingInterval();
    // Note: Browser WebSocket doesn't support ping/pong
    // We use a heartbeat interval instead to check connection status
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        // Browser WebSocket doesn't have ping method
        // Just check connection status
        console.log('[TaskWebSocket] Heartbeat - connection alive');
      }
    }, 30000);
  }

  /**
   * Stop ping interval
   */
  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}

// Export singleton instance
export const taskProgressClient = new TaskProgressClient();
