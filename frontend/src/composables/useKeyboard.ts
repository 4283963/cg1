import { ref, onMounted, onUnmounted } from 'vue';

export interface KeySequence {
  keys: string[];
  timestamp: number;
}

const KEY_DEBOUNCE_MS = 15;
const MAX_KEYS_PER_SECOND = 60;

export function useKeyboard(
  onKeyPress?: (key: string) => void,
  onSequence?: (sequence: string[]) => void
) {
  const pressedKeys = ref<Set<string>>(new Set());
  const keyHistory = ref<string[]>([]);
  const activeSequences = ref<KeySequence[]>([]);
  const droppedKeys = ref<number>(0);
  const sequenceTimeout = 400;

  let lastKeyTime = 0;
  let lastKeyProcessTime = 0;
  let currentSequence: string[] = [];
  let sequenceTimer: ReturnType<typeof setTimeout> | null = null;
  let keyCountWindow: number[] = [];

  const validKeys = new Set([
    'W', 'A', 'S', 'D', 'Q', 'E',
    'U', 'I', 'O', 'P',
    'J', 'K', 'L',
    'N', 'M',
    'V', 'B'
  ]);

  function normalizeKey(key: string): string {
    return key.toUpperCase();
  }

  function isKeyValid(key: string): boolean {
    return validKeys.has(key);
  }

  function checkKeyRateLimit(): boolean {
    const now = Date.now();
    const cutoff = now - 1000;
    keyCountWindow = keyCountWindow.filter(t => t >= cutoff);

    if (keyCountWindow.length >= MAX_KEYS_PER_SECOND) {
      droppedKeys.value++;
      return false;
    }

    keyCountWindow.push(now);
    return true;
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.repeat) return;

    const key = normalizeKey(event.key);
    
    if (!isKeyValid(key)) return;

    event.preventDefault();
    
    const now = Date.now();

    if (now - lastKeyProcessTime < KEY_DEBOUNCE_MS) {
      return;
    }

    if (!checkKeyRateLimit()) {
      return;
    }

    lastKeyProcessTime = now;
    pressedKeys.value.add(key);
    
    if (now - lastKeyTime > sequenceTimeout) {
      currentSequence = [];
    }
    lastKeyTime = now;

    currentSequence.push(key);
    if (currentSequence.length > 3) {
      currentSequence = currentSequence.slice(-3);
    }

    keyHistory.value.push(key);
    if (keyHistory.value.length > 20) {
      keyHistory.value = keyHistory.value.slice(-20);
    }

    if (sequenceTimer) {
      clearTimeout(sequenceTimer);
    }
    sequenceTimer = setTimeout(() => {
      if (currentSequence.length > 0 && onSequence) {
        onSequence([...currentSequence]);
      }
      currentSequence = [];
    }, sequenceTimeout);

    if (onKeyPress) {
      onKeyPress(key);
    }
  }

  function handleKeyUp(event: KeyboardEvent) {
    const key = normalizeKey(event.key);
    pressedKeys.value.delete(key);
  }

  function handleBlur() {
    pressedKeys.value.clear();
  }

  function clearHistory() {
    keyHistory.value = [];
    currentSequence = [];
    activeSequences.value = [];
    keyCountWindow = [];
    droppedKeys.value = 0;
  }

  function isKeyPressed(key: string): boolean {
    return pressedKeys.value.has(normalizeKey(key));
  }

  onMounted(() => {
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);
  });

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeyDown);
    window.removeEventListener('keyup', handleKeyUp);
    window.removeEventListener('blur', handleBlur);
    
    if (sequenceTimer) {
      clearTimeout(sequenceTimer);
    }
  });

  return {
    pressedKeys,
    keyHistory,
    activeSequences,
    droppedKeys,
    isKeyPressed,
    clearHistory
  };
}

