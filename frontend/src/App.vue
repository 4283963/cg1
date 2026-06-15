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

        <div class="panel-section heat-panel">
          <h3 class="panel-title">
            <span class="heat-icon">🔥</span>
            灯光烤炙
          </h3>
          
          <div class="heat-info">
            <div class="heat-stat">
              <span class="stat-label">演出时长</span>
              <span class="stat-value">{{ formatTime(heatState.performance_time) }}</span>
            </div>
            <div class="heat-stat">
              <span class="stat-label">热量级别</span>
              <span class="stat-value" :style="{ color: heatColor }">
                {{ (heatState.heat_level * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="heat-stat">
              <span class="stat-label">材质变软</span>
              <span class="stat-value" :style="{ color: softnessColor }">
                {{ (heatState.softness * 100).toFixed(0) }}%
              </span>
            </div>
          </div>

          <div class="heat-visual">
            <div class="heat-progress-bg">
              <div 
                class="heat-progress-fill"
                :style="{ width: heatState.heat_level * 100 + '%', background: heatGradient }"
              ></div>
              <div 
                class="heat-softness-indicator"
                :style="{ left: heatState.softness * 100 + '%' }"
                title="变软程度"
              >
                <div class="indicator-line"></div>
                <span class="indicator-label">💧</span>
              </div>
            </div>
            <div class="heat-labels">
              <span>柔韧</span>
              <span>松弛</span>
              <span>融化</span>
            </div>
          </div>

          <div class="control-group">
            <label style="font-size: 12px; color: var(--text-secondary);">
              手动调节热量: {{ (heatState.heat_level * 100).toFixed(0) }}%
            </label>
            <input 
              type="range" 
              min="0" 
              max="1" 
              step="0.01"
              :value="heatState.heat_level"
              @input="handleHeatLevelChange"
              style="width: 100%;"
            />
          </div>

          <div class="control-group heat-buttons">
            <button 
              class="btn"
              :class="{ active: heatState.is_heat_on }"
              @click="toggleHeat"
              style="flex: 1;"
            >
              {{ heatState.is_heat_on ? '🔥 加热中' : '⏸️ 暂停' }}
            </button>
            <button 
              class="btn btn-secondary"
              @click="handleHeatReset"
              style="flex: 1;"
            >
              ❄️ 冷却
            </button>
          </div>

          <div class="heat-effect">
            <p style="font-size: 11px; color: var(--text-secondary); margin: 8px 0 0 0; line-height: 1.5;">
              <strong>效果说明：</strong><br>
              随着灯光烤炙时间增加，牛皮材质会逐渐变软，关节弯曲幅度增大，边缘产生波浪形起伏。
            </p>
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
  heatState,
  connect,
  disconnect,
  sendKeyPress,
  sendKeySequence,
  sendReset,
  sendHeatOn,
  sendHeatLevel,
  sendHeatReset,
  onFrame,
  onAction,
  onHeat
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
  setSoftness,
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

const heatColor = computed(() => {
  const level = heatState.value.heat_level;
  if (level < 0.3) return '#4ade80';
  if (level < 0.6) return '#fbbf24';
  return '#ef4444';
});

const softnessColor = computed(() => {
  const level = heatState.value.softness;
  if (level < 0.2) return '#60a5fa';
  if (level < 0.5) return '#a78bfa';
  return '#f472b6';
});

const heatGradient = computed(() => {
  return 'linear-gradient(90deg, #4ade80 0%, #fbbf24 50%, #ef4444 100%)';
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

onHeat((heat) => {
  setSoftness(heat.softness);
});

function toggleHeat() {
  const newState = !heatState.value.is_heat_on;
  sendHeatOn(newState);
}

function handleHeatLevelChange(event: Event) {
  const target = event.target as HTMLInputElement;
  sendHeatLevel(parseFloat(target.value));
}

function handleHeatReset() {
  sendHeatReset();
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

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

<style scoped>
.heat-panel {
  background: linear-gradient(135deg, rgba(139, 0, 0, 0.1) 0%, rgba(255, 107, 53, 0.05) 100%);
  border: 1px solid rgba(255, 107, 53, 0.2);
}

.heat-icon {
  display: inline-block;
  margin-right: 6px;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.8; }
}

.heat-info {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 15px;
}

.heat-stat {
  flex: 1;
  text-align: center;
  padding: 8px 4px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
}

.stat-label {
  display: block;
  font-size: 10px;
  color: var(--text-secondary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  display: block;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: 'Courier New', monospace;
}

.heat-visual {
  margin-bottom: 15px;
}

.heat-progress-bg {
  position: relative;
  height: 24px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 12px;
  overflow: visible;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.heat-progress-fill {
  height: 100%;
  border-radius: 12px;
  transition: width 0.3s ease;
  box-shadow: 0 0 15px rgba(255, 107, 53, 0.4);
}

.heat-softness-indicator {
  position: absolute;
  top: -4px;
  transform: translateX(-50%);
  transition: left 0.3s ease;
}

.indicator-line {
  width: 2px;
  height: 32px;
  background: #f472b6;
  box-shadow: 0 0 8px #f472b6;
}

.indicator-label {
  position: absolute;
  top: -18px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 12px;
}

.heat-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 10px;
  color: var(--text-secondary);
}

.heat-buttons {
  display: flex;
  gap: 8px;
}

.heat-buttons .btn.active {
  background: linear-gradient(135deg, #ff6b35 0%, #ef4444 100%);
  border-color: #ff6b35;
  box-shadow: 0 0 15px rgba(255, 107, 53, 0.4);
}

.heat-effect {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

input[type="range"] {
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.3);
  outline: none;
}

input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ff6b35 0%, #ef4444 100%);
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
  transition: transform 0.2s ease;
}

input[type="range"]::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

input[type="range"]::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ff6b35 0%, #ef4444 100%);
  cursor: pointer;
  border: none;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
}
</style>
