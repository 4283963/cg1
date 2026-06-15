import { ref, onUnmounted } from 'vue';
import type { 
  ConnectionStatus, 
  WebSocketMessage, 
  OutgoingMessage,
  FrameData,
  ActionAppliedData,
  JointData,
  JointsMap
} from '../types/shadowPuppet';

function expandFrameData(data: any): any {
  const expanded: any = { ...data };

  if ('t' in data) {
    expanded.timestamp = data.t;
    delete expanded.t;
  }
  if ('pt' in data) {
    expanded.physics_time = data.pt;
    delete expanded.pt;
  }
  if ('df' in data) {
    expanded.dropped_frames = data.df;
    delete expanded.df;
  }
  if ('j' in data) {
    const joints: JointsMap = {};
    for (const [jointName, jointData] of Object.entries<any>(data.j)) {
      joints[jointName] = {
        rotation_matrix: jointData.rm || jointData.rotation_matrix || [[1,0,0],[0,1,0],[0,0,1]],
        euler_angles: jointData.ea || jointData.euler_angles || [0, 0, 0],
        angular_velocity: jointData.angular_velocity || [0, 0, 0],
        tension_force: jointData.tension_force || [0, 0, 0],
        position: jointData.position || [0, 0, 0]
      };
    }
    expanded.joints = joints;
    delete expanded.j;
  }

  if ('ct' in data) {
    expanded.client_timestamp = data.ct;
    delete expanded.ct;
  }
  if ('st' in data) {
    expanded.server_timestamp = data.st;
    delete expanded.st;
  }
  if ('f' in data) {
    expanded.frames = data.f;
    delete expanded.f;
  }
  if ('fc' in data) {
    expanded.frame_count = data.fc;
    delete expanded.fc;
  }

  return expanded;
}

function expandBatchFrames(frames: any[]): any[] {
  return frames.map((f: any) => expandFrameData(f));
}

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

  let lastSendTime = 0;
  const MIN_SEND_INTERVAL = 8;
  let sendTimer: ReturnType<typeof setTimeout> | null = null;

  const onFrameCallbacks: ((frame: FrameData) => void)[] = [];
  const onActionCallbacks: ((action: ActionAppliedData) => void)[] = [];

  function onFrame(callback: (frame: FrameData) => void) {
    onFrameCallbacks.push(callback);
  }

  function onAction(callback: (action: ActionAppliedData) => void) {
    onActionCallbacks.push(callback);
  }

  function _flushSendQueue() {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const now = Date.now();
    if (now - lastSendTime < MIN_SEND_INTERVAL) {
      if (!sendTimer) {
        sendTimer = setTimeout(() => {
          sendTimer = null;
          _flushSendQueue();
        }, MIN_SEND_INTERVAL - (now - lastSendTime));
      }
      return;
    }

    while (messageQueue.length > 0) {
      const msg = messageQueue.shift();
      if (msg && ws && ws.readyState === WebSocket.OPEN) {
        const json = JSON.stringify(msg);
        if (json.length > 64 * 1024) {
          console.warn('Outgoing message too large, dropping');
          continue;
        }
        const now2 = Date.now();
        if (now2 - lastSendTime >= MIN_SEND_INTERVAL) {
          ws.send(json);
          lastSendTime = now2;
        } else {
          messageQueue.unshift(msg);
          if (!sendTimer) {
            sendTimer = setTimeout(() => {
              sendTimer = null;
              _flushSendQueue();
            }, MIN_SEND_INTERVAL);
          }
          break;
        }
      }
    }
  }

  function send(message: OutgoingMessage) {
    if (messageQueue.length > 100) {
      messageQueue.shift();
    }
    messageQueue.push(message);
    _flushSendQueue();
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
    _flushSendQueue();
  }

  function handleMessage(event: MessageEvent) {
    try {
      const rawData = JSON.parse(event.data);
      
      switch (rawData.type) {
        case 'frame':
        case 'state': {
          const expanded = expandFrameData(rawData);
          const frameData = rawData.type === 'state' ? { ...expanded, type: 'frame' } : expanded;
          lastFrame.value = frameData;
          onFrameCallbacks.forEach(cb => cb(frameData));
          break;
        }
        case 'action_applied':
          lastAction.value = rawData;
          onActionCallbacks.forEach(cb => cb(rawData));
          break;
        case 'pong': {
          const expanded = expandFrameData(rawData);
          latency.value = Date.now() - (expanded.client_timestamp || 0);
          break;
        }
        case 'reset_complete':
          console.log('Reset complete');
          break;
        case 'batch_result': {
          const expanded = expandFrameData(rawData);
          if (expanded.frames) {
            expanded.frames = expandBatchFrames(expanded.frames);
          }
          console.log(`Received batch result with ${expanded.frame_count || 0} frames`);
          break;
        }
        case 'error':
        case 'warning':
          errorMessage.value = rawData.message;
          console.warn(`Server ${rawData.type}: ${rawData.message}`);
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
