// 前端
class WebSocketClient {
    constructor(url, options = {}) {
        this.url = url;
        this.options = {
            reconnectInterval: 1000,
            maxReconnectAttempts: 5,
            ...options
        };
        this.reconnectAttempts = 0;
        this.connect();
    }

    connect() {
        this.ws = new WebSocket(this.url);
        
        this.ws.onopen = () => {
            console.log('連線成功');
            this.reconnectAttempts = 0;
        };

        this.ws.onclose = () => {
            console.log('連線關閉');
            this.reconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket 錯誤:', error);
        };
    }

    reconnect() {
        if (this.reconnectAttempts < this.options.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`嘗試重新連線... (${this.reconnectAttempts})`);
            setTimeout(() => {
                this.connect();
            }, this.options.reconnectInterval);
        } else {
            console.log('達到最大重連次數');
        }
    }

    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// 使用方式
// const wsClient = new WebSocketClient('ws://your-server-url');
