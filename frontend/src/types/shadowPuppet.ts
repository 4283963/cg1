export interface JointData {
  rotation_matrix: number[][];
  euler_angles: number[];
  angular_velocity: number[];
  tension_force: number[];
  position: number[];
}

export interface FrameData {
  type: 'frame';
  timestamp: number;
  physics_time: number;
  joints: Record<string, JointData>;
}

export interface ActionAppliedData {
  type: 'action_applied';
  sequence: string[];
  timestamp: number;
}

export interface ResetCompleteData {
  type: 'reset_complete';
  timestamp: number;
}

export interface PongData {
  type: 'pong';
  client_timestamp: number;
  server_timestamp: number;
}

export interface StateData {
  type: 'state';
  timestamp: number;
  physics_time: number;
  joints: Record<string, JointData>;
}

export interface BatchResultData {
  type: 'batch_result';
  frames: FrameData[];
  frame_count: number;
}

export interface ErrorData {
  type: 'error' | 'warning';
  message: string;
}

export type WebSocketMessage = 
  | FrameData 
  | ActionAppliedData 
  | ResetCompleteData 
  | PongData 
  | StateData 
  | BatchResultData 
  | ErrorData;

export interface KeyPressMessage {
  type: 'key_press';
  key: string;
  timestamp: number;
}

export interface KeySequenceMessage {
  type: 'key_sequence';
  sequence: string[];
}

export interface ResetMessage {
  type: 'reset';
}

export interface PingMessage {
  type: 'ping';
  timestamp: number;
}

export interface GetStateMessage {
  type: 'get_state';
}

export interface BatchSequenceMessage {
  type: 'batch_sequence';
  sequences: string[][];
  duration: number;
}

export type OutgoingMessage = 
  | KeyPressMessage 
  | KeySequenceMessage 
  | ResetMessage 
  | PingMessage 
  | GetStateMessage 
  | BatchSequenceMessage;

export interface PuppetJoint {
  name: string;
  parent: string | null;
  children: string[];
  position: THREE.Vector3;
  restRotation: THREE.Euler;
}

export interface AnimationState {
  targetRotations: Record<string, THREE.Quaternion>;
  currentRotations: Record<string, THREE.Quaternion>;
  lerpFactor: number;
}

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected';

export interface KeyAction {
  keys: string[];
  description: string;
  target: string;
}
