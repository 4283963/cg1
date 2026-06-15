import asyncio
import json
import time
import math
from typing import Dict, List, Optional, Deque, Any
from collections import deque
from dataclasses import dataclass, field
import websockets
from websockets.server import WebSocketServerProtocol
from .physics_engine import ShadowPuppetPhysics


MAX_FRAME_SIZE_BYTES = 64 * 1024
MIN_FRAME_INTERVAL = 1.0 / 60.0
MAX_PENDING_MESSAGES = 20
KEY_DEBOUNCE_MS = 15.0
MAX_KEYS_PER_SECOND = 60


@dataclass
class ClientSession:
    websocket: WebSocketServerProtocol
    physics: ShadowPuppetPhysics
    key_buffer: List[str] = field(default_factory=list)
    last_key_time: float = 0.0
    is_connected: bool = True
    stream_task: Optional[asyncio.Task] = None
    key_sequence_timeout: float = 0.4

    send_queue: Deque[str] = field(default_factory=deque)
    last_send_time: float = 0.0
    dropped_frames: int = 0
    total_frames_sent: int = 0

    input_queue: Deque[Dict] = field(default_factory=deque)
    input_task: Optional[asyncio.Task] = None
    last_key_process_time: float = 0.0
    key_count_window: Deque[float] = field(default_factory=deque)

    batch_actions: List[List[str]] = field(default_factory=list)
    last_batch_flush: float = 0.0


class ShadowPuppetServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Dict[str, ClientSession] = {}
        self.frame_rate = 60
        self.frame_interval = 1.0 / self.frame_rate

    @staticmethod
    def _serialize_json(data: Any) -> str:
        return json.dumps(data, separators=(',', ':'), ensure_ascii=False)

    @staticmethod
    def _round_float(value: float, decimals: int = 2) -> float:
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return round(float(value), decimals)

    def _trim_frame_data(self, joints_data: Dict[str, Dict]) -> Dict[str, Dict]:
        trimmed = {}
        for joint_name, joint in joints_data.items():
            trimmed[joint_name] = {
                'rm': joint.get('rotation_matrix', [[1,0,0],[0,1,0],[0,0,1]]),
                'ea': joint.get('euler_angles', [0, 0, 0])
            }
        return trimmed

    def _expand_frame_data(self, trimmed: Dict[str, Dict]) -> Dict[str, Dict]:
        expanded = {}
        for joint_name, joint in trimmed.items():
            expanded[joint_name] = {
                'rotation_matrix': joint.get('rm', [[1,0,0],[0,1,0],[0,0,1]]),
                'euler_angles': joint.get('ea', [0, 0, 0])
            }
        return expanded

    async def _safe_send(self, session: ClientSession, message: str, high_priority: bool = False) -> bool:
        try:
            msg_size = len(message.encode('utf-8'))
            if msg_size > MAX_FRAME_SIZE_BYTES:
                print(f"[WARNING] Message too large ({msg_size} bytes), dropping")
                return False

            if high_priority:
                session.last_send_time = time.time()
                session.total_frames_sent += 1
                await session.websocket.send(message)
                return True

            current_time = time.time()
            time_since_last = current_time - session.last_send_time
            if time_since_last < MIN_FRAME_INTERVAL * 0.5:
                if len(session.send_queue) < MAX_PENDING_MESSAGES:
                    session.send_queue.append(message)
                    return True
                else:
                    session.dropped_frames += 1
                    if session.dropped_frames % 100 == 0:
                        print(f"[WARNING] Dropped {session.dropped_frames} frames total")
                    return False

            session.last_send_time = current_time
            session.total_frames_sent += 1
            await session.websocket.send(message)
            return True
        except websockets.exceptions.ConnectionClosed:
            session.is_connected = False
            return False
        except Exception as e:
            print(f"[ERROR] Send failed: {e}")
            return False

    async def _flush_send_queue(self, session: ClientSession):
        while session.send_queue and session.is_connected:
            current_time = time.time()
            if current_time - session.last_send_time >= MIN_FRAME_INTERVAL * 0.5:
                message = session.send_queue.popleft()
                session.last_send_time = current_time
                session.total_frames_sent += 1
                try:
                    await session.websocket.send(message)
                except websockets.exceptions.ConnectionClosed:
                    session.is_connected = False
                    break
                except Exception:
                    break
            else:
                break

    def _check_key_rate_limit(self, session: ClientSession) -> bool:
        current_time = time.time()
        cutoff = current_time - 1.0
        while session.key_count_window and session.key_count_window[0] < cutoff:
            session.key_count_window.popleft()

        if len(session.key_count_window) >= MAX_KEYS_PER_SECOND:
            return False

        session.key_count_window.append(current_time)
        return True

    async def handle_client(self, websocket: WebSocketServerProtocol):
        client_id = f"client_{id(websocket)}"
        print(f"[INFO] New client connected: {client_id}")

        session = ClientSession(
            websocket=websocket,
            physics=ShadowPuppetPhysics()
        )
        self.clients[client_id] = session

        try:
            session.stream_task = asyncio.create_task(self._stream_physics_data(client_id, session))
            session.input_task = asyncio.create_task(self._process_input_queue(client_id, session))

            async for message in websocket:
                try:
                    if len(message.encode('utf-8')) > MAX_FRAME_SIZE_BYTES:
                        print(f"[WARNING] Incoming message too large from {client_id}, ignoring")
                        continue

                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        continue

                    if len(session.input_queue) < MAX_PENDING_MESSAGES:
                        session.input_queue.append(data)
                    else:
                        pass
                except Exception as e:
                    print(f"[ERROR] Error processing incoming message: {e}")

        except websockets.exceptions.ConnectionClosed:
            print(f"[INFO] Client disconnected: {client_id}")
        finally:
            session.is_connected = False
            if session.stream_task:
                session.stream_task.cancel()
            if session.input_task:
                session.input_task.cancel()
            if client_id in self.clients:
                del self.clients[client_id]
            print(f"[INFO] Client session cleaned up: {client_id}")

    async def _process_input_queue(self, client_id: str, session: ClientSession):
        try:
            while session.is_connected:
                if session.input_queue:
                    data = session.input_queue.popleft()
                    try:
                        await self._handle_message(client_id, session, data)
                    except Exception as e:
                        print(f"[ERROR] Error handling message from {client_id}: {e}")
                else:
                    await asyncio.sleep(0.002)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[ERROR] Input processor error for {client_id}: {e}")

    async def _handle_message(self, client_id: str, session: ClientSession, data: Dict):
        msg_type = data.get("type")

        if msg_type == "key_press":
            await self._handle_key_press(session, data)
        elif msg_type == "key_sequence":
            await self._handle_key_sequence(session, data)
        elif msg_type == "reset":
            await self._handle_reset(session)
        elif msg_type == "ping":
            await self._handle_ping(session, data)
        elif msg_type == "get_state":
            await self._handle_get_state(session)
        elif msg_type == "batch_sequence":
            await self._handle_batch_sequence(session, data)
        elif msg_type == "heat_on":
            await self._handle_heat_on(session, data)
        elif msg_type == "heat_level":
            await self._handle_heat_level(session, data)
        elif msg_type == "heat_reset":
            await self._handle_heat_reset(session, data)

    async def _handle_key_press(self, session: ClientSession, data: Dict):
        key = data.get("key", "").upper()
        timestamp = data.get("timestamp", time.time())

        if not key or len(key) > 2:
            return

        current_time = time.time()

        debounce_threshold = KEY_DEBOUNCE_MS / 1000.0
        if current_time - session.last_key_process_time < debounce_threshold:
            return

        if not self._check_key_rate_limit(session):
            return

        session.last_key_process_time = current_time

        if current_time - session.last_key_time > session.key_sequence_timeout:
            session.key_buffer = []

        session.key_buffer.append(key)
        session.last_key_time = current_time

        if len(session.key_buffer) > 3:
            session.key_buffer = session.key_buffer[-3:]

        applied = False
        for seq_len in range(min(len(session.key_buffer), 3), 0, -1):
            test_sequence = session.key_buffer[-seq_len:]
            if session.physics.apply_key_sequence(test_sequence):
                applied = True
                ack_msg = self._serialize_json({
                    "type": "action_applied",
                    "sequence": test_sequence,
                    "timestamp": self._round_float(current_time, 3)
                })
                await self._safe_send(session, ack_msg, high_priority=True)
                break

        if not applied and len(key) == 1:
            session.physics.apply_key_sequence([key])

    async def _handle_key_sequence(self, session: ClientSession, data: Dict):
        sequence = data.get("sequence", [])
        if not isinstance(sequence, list) or not sequence:
            return

        sequence = [k.upper() for k in sequence if isinstance(k, str)]
        if not sequence:
            return

        if not self._check_key_rate_limit(session):
            return

        if session.physics.apply_key_sequence(sequence):
            ack_msg = self._serialize_json({
                "type": "action_applied",
                "sequence": sequence,
                "timestamp": self._round_float(time.time(), 3)
            })
            await self._safe_send(session, ack_msg, high_priority=True)
        else:
            warning_msg = self._serialize_json({
                "type": "warning",
                "message": f"Unknown sequence: {sequence}"
            })
            await self._safe_send(session, warning_msg, high_priority=True)

    async def _handle_reset(self, session: ClientSession):
        session.physics.reset()
        session.key_buffer = []
        session.dropped_frames = 0
        reset_msg = self._serialize_json({
            "type": "reset_complete",
            "timestamp": self._round_float(time.time(), 3)
        })
        await self._safe_send(session, reset_msg, high_priority=True)

    async def _handle_heat_on(self, session: ClientSession, data: Dict):
        on = data.get("on", True)
        session.physics.set_heat_on(on)
        ack_msg = self._serialize_json({
            "type": "heat_ack",
            "on": on,
            "timestamp": self._round_float(time.time(), 3)
        })
        await self._safe_send(session, ack_msg, high_priority=True)

    async def _handle_heat_level(self, session: ClientSession, data: Dict):
        level = float(data.get("level", 0.0))
        session.physics.set_heat_level(level)
        session.physics.set_heat_on(True)
        ack_msg = self._serialize_json({
            "type": "heat_ack",
            "level": self._round_float(level, 3),
            "timestamp": self._round_float(time.time(), 3)
        })
        await self._safe_send(session, ack_msg, high_priority=True)

    async def _handle_heat_reset(self, session: ClientSession, data: Dict):
        session.physics.reset_heat()
        ack_msg = self._serialize_json({
            "type": "heat_ack",
            "reset": True,
            "timestamp": self._round_float(time.time(), 3)
        })
        await self._safe_send(session, ack_msg, high_priority=True)

    async def _handle_ping(self, session: ClientSession, data: Dict):
        pong_msg = self._serialize_json({
            "type": "pong",
            "ct": self._round_float(data.get("timestamp", 0), 3),
            "st": self._round_float(time.time(), 3)
        })
        await self._safe_send(session, pong_msg, high_priority=True)

    async def _handle_get_state(self, session: ClientSession):
        joints_data = session.physics._get_joint_rotations()
        trimmed_joints = self._trim_frame_data(joints_data)
        state_msg = self._serialize_json({
            "type": "state",
            "t": self._round_float(time.time(), 3),
            "pt": self._round_float(session.physics.time, 3),
            "j": trimmed_joints
        })
        await self._safe_send(session, state_msg)

    async def _handle_batch_sequence(self, session: ClientSession, data: Dict):
        sequences = data.get("sequences", [])
        duration = data.get("duration", 2.0)

        if not isinstance(sequences, list):
            return

        results = session.physics.simulate(sequences, duration)
        trimmed_results = [self._trim_frame_data(r) for r in results]
        batch_msg = self._serialize_json({
            "type": "batch_result",
            "f": trimmed_results,
            "fc": len(trimmed_results)
        })
        await self._safe_send(session, batch_msg)

    async def _stream_physics_data(self, client_id: str, session: ClientSession):
        frame_counter = 0
        try:
            while session.is_connected:
                start_time = time.time()

                step_result = session.physics.step()
                joints_data = step_result['joints']
                heat_state = step_result['heat']
                trimmed_joints = self._trim_frame_data(joints_data)

                frame_counter += 1

                payload = {
                    "type": "frame",
                    "t": self._round_float(time.time(), 3),
                    "pt": self._round_float(session.physics.time, 3),
                    "j": trimmed_joints,
                    "h": {
                        "t": heat_state.get('performance_time', 0),
                        "hl": heat_state.get('heat_level', 0),
                        "s": heat_state.get('softness', 0),
                        "on": heat_state.get('is_heat_on', True)
                    }
                }

                if frame_counter % 60 == 0 and session.dropped_frames > 0:
                    payload["df"] = session.dropped_frames

                frame_msg = self._serialize_json(payload)

                msg_size = len(frame_msg.encode('utf-8'))
                if msg_size > MAX_FRAME_SIZE_BYTES:
                    compact_joints = {}
                    for jn, jd in trimmed_joints.items():
                        compact_joints[jn] = {'ea': jd.get('ea', [0, 0, 0])}
                    payload["j"] = compact_joints
                    frame_msg = self._serialize_json(payload)

                await self._safe_send(session, frame_msg)
                await self._flush_send_queue(session)

                elapsed = time.time() - start_time
                sleep_time = self.frame_interval - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            print(f"[INFO] Stream task cancelled for {client_id}")
        except Exception as e:
            print(f"[ERROR] Stream error for {client_id}: {e}")

    async def start(self):
        print(f"[INFO] Starting Shadow Puppet WebSocket server on {self.host}:{self.port}")
        print(f"[INFO] Frame size limit: {MAX_FRAME_SIZE_BYTES} bytes")
        print(f"[INFO] Max keys/sec: {MAX_KEYS_PER_SECOND}, Debounce: {KEY_DEBOUNCE_MS}ms")
        async with websockets.serve(self.handle_client, self.host, self.port):
            print(f"[INFO] Server started successfully. Waiting for clients...")
            await asyncio.Future()

    def run(self):
        asyncio.run(self.start())
