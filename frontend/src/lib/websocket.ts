/**
 * WebSocket Client for Real-time Chat
 * Handles WebSocket connection, message sending/receiving, and auto-reconnect
 */

export interface WebSocketMessage {
  type: 'status' | 'assistant_message' | 'error' | 'ping' | 'pong' | 'video_load_confirmation' | 'video_load_status';
  message?: string;
  content?: string;
  code?: string;
  // Video load specific fields
  youtube_url?: string;
  video_id?: string;
  video_title?: string;
  status?: 'started' | 'completed' | 'failed';
  error?: string;
}

export interface IncomingMessage {
  conversation_id?: string;
  content: string;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private token: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private messageHandlers: ((data: WebSocketMessage) => void)[] = [];
  private errorHandlers: ((error: Error) => void)[] = [];
  private isManualClose = false;

  constructor(url: string, token: string) {
    this.url = url;
    this.token = token;
  }

  /**
   * Connect to WebSocket server
   */
  connect(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    this.isManualClose = false;
    const wsUrl = `${this.url}?token=${this.token}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
      };

      this.ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);

          // Handle ping/pong for keepalive
          if (data.type === 'ping') {
            this.send({ type: 'pong' });
            return;
          }

          // Notify all message handlers
          this.messageHandlers.forEach(handler => handler(data));
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.errorHandlers.forEach(handler =>
          handler(new Error('WebSocket connection error'))
        );
      };

      this.ws.onclose = () => {
        console.log('WebSocket closed');
        if (!this.isManualClose) {
          this.reconnect();
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.reconnect();
    }
  }

  /**
   * Send a message through WebSocket
   */
  sendMessage(content: string, conversationId?: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      this.errorHandlers.forEach(handler =>
        handler(new Error('WebSocket not connected'))
      );
      return;
    }

    const message: IncomingMessage = {
      content,
      ...(conversationId && { conversation_id: conversationId })
    };

    this.ws.send(JSON.stringify(message));
  }

  /**
   * Send raw data (for ping/pong)
   */
  private send(data: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  /**
   * Register a message handler
   */
  onMessage(callback: (data: WebSocketMessage) => void): void {
    this.messageHandlers.push(callback);
  }

  /**
   * Register an error handler
   */
  onError(callback: (error: Error) => void): void {
    this.errorHandlers.push(callback);
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect(): void {
    this.isManualClose = true;

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Auto-reconnect with exponential backoff
   */
  private reconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.errorHandlers.forEach(handler =>
        handler(new Error('Failed to reconnect after multiple attempts'))
      );
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}
