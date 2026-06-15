<template>
  <div class="app-container">
    <header class="header">
      <h1>皮影戏数字化保存与远程提线演练系统</h1>
      <div class="connection-status">
        <span 
          class="status-indicator"
          :class="status"
        ></span>
        <span>{{ statusText }}</span>
        <span v-if="latency > 0" style="color: var(--text-secondary); margin-left: 10px;">
          延迟: {{ latency }}ms
        </span>
      </div>
    </header>

    <div class="main-content">
      <div class="viewer-container">
        <div 
          ref="canvasContainer" 
          id="canvas-container"
          tabindex="0"
        ></div>

        <div v-if="!isInitialized" class="loading-overlay">
          <div class="loading-spinner"></div>
          <div class="loading-text">正在加载3D皮影模型...</div>
        </div>

        <div class="overlay-info">
          <div class="info-item">
            <span class="label">FPS</span>
            <span class="value">{{ fps }}</span>
          </div>
          <div class="info-item">
            <span class="label">物理时间</span>
            <span class="value">{{ physicsTime.toFixed(2) }}s</span>
          </div>
          <div class="info-item">
            <span class="label">渲染帧</span>
            <span class="value">{{ frameCount }}</span>
          </div>
        </div>

        <div class="key-hint">
          <span 
            v-for="key in displayKeys" 
            :key="key"
            class="key-tag"
            :class="{ active: isKeyPressed(key) }"
          >
            {{ key }}
          </span>
        </div>
      </div>

      <aside class="side-panel">
        <div class="panel-section">
          <h3 class="panel-title">连接控制</h3>
          <div class="control-group">
            <button 
              class="btn"
              @click="toggleConnection"
            >
              {{ status === 'connected' ? '断开连接' : '连接后端' }}
            </button>
            <button 
              class="btn btn-secondary"
              @click="handleReset"
            >
              重置皮影姿态
            </button>
          </div>
        </div>

        <div class="panel-section">
          <h3 class="panel-title">按键序列</h3>
          <div class="key-history">
            <span 
              v-for="(key, index) in recentKeys" 
              :key="index"
              class="history-key"
            >
              {{ key }}
            </span>
            <span v-if="recentKeys.length === 0" style="color: var(--text-secondary); font-size: 11px;">
              按下键盘按键开始操作...
            </span>
          </div>
        </div>

        <div class="panel-section">
          <h3 class="panel-title">快速动作</h3>
          <div class="sequence-buttons">
            <button 
              v-for="seq in quickSequences" 
              :key="seq.keys.join('')"
              class="seq-btn"
              @click="sendSequence(seq.keys)"
            >
              <span class="keys">{{ seq.keys.join(' → ') }}</span>
              <span class="desc">{{ seq.desc }}</span>
            </button>
          </div>
        </div>

        <div class="panel-section">
          <h3 class="panel-title">关节状态</h3>
          <div class="joint-states">
            <div 
              v-for="(angles, joint) in keyJoints" 
              :key="joint"
              class="joint-item"
            >
              <span class="joint-name">{{ jointNames[joint] || joint }}</span>
              <span class="joint-angles">
                {{ angles[0] }}° {{ angles[1] }}° {{ angles[2] }}°
              </span>
            </div>
          </div>
        </div>

        <div class="panel-section">
          <h3 class="panel-title">动画参数</h3>
          <div class="control-group">
            <label style="font-size: 12px; color: var(--text-secondary);">
              平滑度: {{ smoothness.toFixed(2) }}
            </label>
            <input 
              type="range" 
              min="0.01" 
              max="1" 
              step="0.01"
              :value="smoothness"
              @input="handleSmoothnessChange"
              style="width: 100%;"
            />
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useWebSocket } from './composables/useWebSocket';
import { useKeyboard } from './composables/useKeyboard';
import { useShadowPuppetRenderer } from './composables/useShadowPuppetRenderer';

const canvasContainer = ref<HTMLElement | null>(null);
const physicsTime = ref(0);
const smoothness = ref(0.12);

const {
  status,
  latency,
  lastFrame,
  connect,
  disconnect,
  sendKeyPress,
  sendKeySequence,
  sendReset,
  onFrame,
  onAction
} = useWebSocket();

const {
  pressedKeys,
  keyHistory,
  isKeyPressed,
  clearHistory
} = useKeyboard(
  (key) => {
    if (status.value === 'connected') {
      sendKeyPress(key);
    }
  },
  (sequence) => {
    if (status.value === 'connected') {
      sendKeySequence(sequence);
    }
  }
);

const {
  isInitialized,
  frameCount,
  fps,
  init,
  dispose,
  updateJointsFromFrame,
  resetPuppet,
  setSmoothness,
  getJointAngles
} = useShadowPuppetRenderer();

const statusText = computed(() => {
  switch (status.value) {
    case 'connected': return '已连接';
    case 'connecting': return '连接中...';
    case 'disconnected': return '未连接';
    default: return '未知';
  }
});

const displayKeys = ['W', 'A', 'S', 'D', 'Q', 'E', 'U', 'I', 'J', 'K', 'N', 'M', 'V', 'B'];

const recentKeys = computed(() => {
  return keyHistory.value.slice(-8);
});

const quickSequences = [
  { keys: ['W', 'J'], desc: '左手扬起' },
  { keys: ['W', 'K'], desc: '右手扬起' },
  { keys: ['J', 'K'], desc: '双手张开' },
  { keys: ['S', 'N'], desc: '左腿抬起' },
  { keys: ['S', 'M'], desc: '右腿抬起' },
  { keys: ['W', 'U', 'J'], desc: '左拳出击' },
  { keys: ['W', 'I', 'K'], desc: '右拳出击' },
  { keys: ['W'], desc: '上身前倾' },
];

const jointNames: Record<string, string> = {
  left_elbow: '左手肘',
  right_elbow: '右手肘',
  left_knee: '左膝盖',
  right_knee: '右膝盖',
  spine: '脊椎',
  head: '头部',
  left_shoulder: '左肩',
  right_shoulder: '右肩',
};

const keyJoints = computed(() => {
  const allAngles = getJointAngles();
  const filtered: Record<string, number[]> = {};
  for (const key of Object.keys(jointNames)) {
    if (allAngles[key]) {
      filtered[key] = allAngles[key];
    }
  }
  return filtered;
});

function toggleConnection() {
  if (status.value === 'connected') {
    disconnect();
  } else {
    connect('ws://localhost:8765');
  }
}

function handleReset() {
  clearHistory();
  if (status.value === 'connected') {
    sendReset();
  }
  resetPuppet();
}

function sendSequence(sequence: string[]) {
  if (status.value === 'connected') {
    sendKeySequence(sequence);
  }
}

function handleSmoothnessChange(event: Event) {
  const target = event.target as HTMLInputElement;
  const value = parseFloat(target.value);
  smoothness.value = value;
  setSmoothness(value);
}

watch(lastFrame, (frame) => {
  if (frame) {
    physicsTime.value = frame.physics_time;
    updateJointsFromFrame(frame);
  }
});

onAction((action) => {
  console.log('Action applied:', action.sequence);
});

onFrame((frame) => {
  physicsTime.value = frame.physics_time;
});

onMounted(() => {
  if (canvasContainer.value) {
    init(canvasContainer.value);
  }
  
  setTimeout(() => {
    connect('ws://localhost:8765');
  }, 1000);
});

onUnmounted(() => {
  disconnect();
  dispose();
});
</script>
