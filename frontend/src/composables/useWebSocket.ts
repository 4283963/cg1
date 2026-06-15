import { ref, onUnmounted } from 'vue';
import type { 
  ConnectionStatus, 
  WebSocketMessage, 
  OutgoingMessage,
  FrameData,
  ActionAppliedData 
} from '../types/shadowPuppet';

export function useWebSocket() {
  const status = ref<ConnectionStatus>('disconnected');
  const latency = ref<number>(0);
  const lastFrame = ref<FrameData | null>(null);
  const lastAction = ref<ActionAppliedData | null>(null);
  const errorMessage = ref<string>('');

  let ws: WebSocket | null = null;
  let pingInterval: ReturnType<typeof setInterval> | null = null;
  let reconnectAttempts = 0;
  let shouldReconnect = true;
  let messageQueue: OutgoingMessage[] = [];

  const onFrameCallbacks: ((frame: FrameData) => void)[] = [];
  const onActionCallbacks: ((action: ActionAppliedData) => void)[] = [];

  function onFrame(callback: (frame: FrameData) => void) {
    onFrameCallbacks.push(callback);
  }

  function onAction(callback: (action: ActionAppliedData) => void) {
    onActionCallbacks.push(callback);
  }

  function send(message: OutgoingMessage) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    } else {
      messageQueue.push(message);
      if (messageQueue.length > 100) {
        messageQueue.shift();
      }
    }
  }

  function sendKeyPress(key: string) {
    send({
      type: 'key_press',
      key: key.toUpperCase(),
      timestamp: Date.now()
    });
  }

  function sendKeySequence(sequence: string[]) {
    send({
      type: 'key_sequence',
      sequence: sequence.map(k => k.toUpperCase())
    });
  }

  function sendReset() {
    send({ type: 'reset' });
  }

  function sendPing() {
    send({
      type: 'ping',
      timestamp: Date.now()
    });
  }

  function flushQueue() {
    while (messageQueue.length > 0 && ws && ws.readyState === WebSocket.OPEN) {
      const msg = messageQueue.shift();
      if (msg) {
        ws.send(JSON.stringify(msg));
      }
    }
  }

  function handleMessage(event: MessageEvent) {
    try {
      const data: WebSocketMessage = JSON.parse(event.data);
      
      switch (data.type) {
        case 'frame':
          lastFrame.value = data;
          onFrameCallbacks.forEach(cb => cb(data));
          break;
        case 'action_applied':
          lastAction.value = data;
          onActionCallbacks.forEach(cb => cb(data));
          break;
        case 'pong':
          latency.value = Date.now() - data.client_timestamp;
          break;
        case 'reset_complete':
          console.log('Reset complete');
          break;
        case 'state':
          lastFrame.value = {
            ...data,
            type: 'frame'
          };
          onFrameCallbacks.forEach(cb => cb(lastFrame.value!));
          break;
        case 'batch_result':
          console.log(`Received batch result with ${data.frame_count} frames`);
          break;
        case 'error':
        case 'warning':
          errorMessage.value = data.message;
          console.warn(`Server ${data.type}: ${data.message}`);
          break;
      }
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e);
    }
  }

  function connect(url: string = 'ws://localhost:8765') {
    if (ws) {
      ws.close();
    }

    shouldReconnect = true;
    status.value = 'connecting';
    errorMessage.value = '';

    try {
      ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('WebSocket connected');
        status.value = 'connected';
        reconnectAttempts = 0;
        flushQueue();

        pingInterval = setInterval(() => {
          sendPing();
        }, 3000);
      };

      ws.onmessage = handleMessage;

      ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        status.value = 'disconnected';
        
        if (pingInterval) {
          clearInterval(pingInterval);
          pingInterval = null;
        }

        if (shouldReconnect && reconnectAttempts < 10) {
          reconnectAttempts++;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);
          setTimeout(() => {
            if (shouldReconnect) {
              connect(url);
            }
          }, delay);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        errorMessage.value = 'Connection error';
      };
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
      status.value = 'disconnected';
      errorMessage.value = 'Failed to connect';
    }
  }

  function disconnect() {
    shouldReconnect = false;
    if (pingInterval) {
      clearInterval(pingInterval);
      pingInterval = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
    status.value = 'disconnected';
  }

  onUnmounted(() => {
    disconnect();
  });

  return {
    status,
    latency,
    lastFrame,
    lastAction,
    errorMessage,
    connect,
    disconnect,
    send,
    sendKeyPress,
    sendKeySequence,
    sendReset,
    onFrame,
    onAction
  };
}
