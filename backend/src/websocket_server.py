import asyncio
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
import websockets
from websockets.server import WebSocketServerProtocol
from .physics_engine import ShadowPuppetPhysics


@dataclass
class ClientSession:
    websocket: WebSocketServerProtocol
    physics: ShadowPuppetPhysics
    key_buffer: List[str]
    last_key_time: float
    is_connected: bool
    stream_task: Optional[asyncio.Task] = None
    key_sequence_timeout: float = 0.4


class ShadowPuppetServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Dict[str, ClientSession] = {}
        self.frame_rate = 60
        self.frame_interval = 1.0 / self.frame_rate

    async def handle_client(self, websocket: WebSocketServerProtocol):
        client_id = f"client_{id(websocket)}"
        print(f"[INFO] New client connected: {client_id}")

        session = ClientSession(
            websocket=websocket,
            physics=ShadowPuppetPhysics(),
            key_buffer=[],
            last_key_time=0.0,
            is_connected=True
        )
        self.clients[client_id] = session

        try:
            session.stream_task = asyncio.create_task(self._stream_physics_data(client_id, session))

            async for message in websocket:
                try:
                    await self._handle_message(client_id, session, message)
                except Exception as e:
                    print(f"[ERROR] Error handling message from {client_id}: {e}")
                    error_msg = json.dumps({
                        "type": "error",
                        "message": str(e)
                    })
                    await websocket.send(error_msg)

        except websockets.exceptions.ConnectionClosed:
            print(f"[INFO] Client disconnected: {client_id}")
        finally:
            session.is_connected = False
            if session.stream_task:
                session.stream_task.cancel()
            del self.clients[client_id]
            print(f"[INFO] Client session cleaned up: {client_id}")

    async def _handle_message(self, client_id: str, session: ClientSession, message: str):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON: {message[:100]}")

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
        else:
            raise ValueError(f"Unknown message type: {msg_type}")

    async def _handle_key_press(self, session: ClientSession, data: Dict):
        key = data.get("key", "").upper()
        timestamp = data.get("timestamp", time.time())

        if not key or len(key) > 2:
            return

        current_time = time.time()
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
                ack_msg = json.dumps({
                    "type": "action_applied",
                    "sequence": test_sequence,
                    "timestamp": current_time
                })
                await session.websocket.send(ack_msg)
                break

        if not applied and len(key) == 1:
            if session.physics.apply_key_sequence([key]):
                pass

    async def _handle_key_sequence(self, session: ClientSession, data: Dict):
        sequence = data.get("sequence", [])
        if not isinstance(sequence, list) or not sequence:
            raise ValueError("Invalid key sequence")

        sequence = [k.upper() for k in sequence if isinstance(k, str)]

        if not session.physics.apply_key_sequence(sequence):
            error_msg = json.dumps({
                "type": "warning",
                "message": f"Unknown sequence: {sequence}"
            })
            await session.websocket.send(error_msg)
        else:
            ack_msg = json.dumps({
                "type": "action_applied",
                "sequence": sequence,
                "timestamp": time.time()
            })
            await session.websocket.send(ack_msg)

    async def _handle_reset(self, session: ClientSession):
        session.physics.reset()
        session.key_buffer = []
        reset_msg = json.dumps({
            "type": "reset_complete",
            "timestamp": time.time()
        })
        await session.websocket.send(reset_msg)

    async def _handle_ping(self, session: ClientSession, data: Dict):
        pong_msg = json.dumps({
            "type": "pong",
            "client_timestamp": data.get("timestamp", 0),
            "server_timestamp": time.time()
        })
        await session.websocket.send(pong_msg)

    async def _handle_get_state(self, session: ClientSession):
        joints_data = session.physics._get_joint_rotations()
        state_msg = json.dumps({
            "type": "state",
            "timestamp": time.time(),
            "physics_time": session.physics.time,
            "joints": joints_data
        })
        await session.websocket.send(state_msg)

    async def _handle_batch_sequence(self, session: ClientSession, data: Dict):
        sequences = data.get("sequences", [])
        duration = data.get("duration", 2.0)

        if not isinstance(sequences, list):
            raise ValueError("Invalid sequences format")

        results = session.physics.simulate(sequences, duration)
        batch_msg = json.dumps({
            "type": "batch_result",
            "frames": results,
            "frame_count": len(results)
        })
        await session.websocket.send(batch_msg)

    async def _stream_physics_data(self, client_id: str, session: ClientSession):
        try:
            while session.is_connected:
                start_time = time.time()

                joints_data = session.physics.step()

                frame_msg = json.dumps({
                    "type": "frame",
                    "timestamp": time.time(),
                    "physics_time": session.physics.time,
                    "joints": joints_data
                })

                try:
                    await session.websocket.send(frame_msg)
                except websockets.exceptions.ConnectionClosed:
                    break

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
        async with websockets.serve(self.handle_client, self.host, self.port):
            print(f"[INFO] Server started successfully. Waiting for clients...")
            await asyncio.Future()

    def run(self):
        asyncio.run(self.start())
