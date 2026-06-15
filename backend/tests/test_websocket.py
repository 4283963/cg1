#!/usr/bin/env python3
import asyncio
import json
import sys
import websockets


async def test_websocket():
    print("=" * 60)
    print("WebSocket 集成测试")
    print("=" * 60)
    print()

    uri = "ws://localhost:8765"
    print(f"连接到: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket 连接成功")
            print()

            print("测试1: 发送 ping...")
            await websocket.send(json.dumps({
                "type": "ping",
                "timestamp": asyncio.get_event_loop().time()
            }))
            
            pong_received = False
            for _ in range(20):
                response = await websocket.recv()
                data = json.loads(response)
                if data["type"] == "pong":
                    pong_received = True
                    break
                elif data["type"] == "frame":
                    continue
                else:
                    print(f"  收到其他消息: {data['type']}")
            
            assert pong_received, "未收到 pong 消息"
            print("✓ Ping-Pong 正常")
            print()

            print("测试2: 发送单键 J (左肘)...")
            await websocket.send(json.dumps({
                "type": "key_press",
                "key": "J",
                "timestamp": asyncio.get_event_loop().time()
            }))
            
            action_received = False
            frame_received = False
            for _ in range(10):
                response = await websocket.recv()
                data = json.loads(response)
                if data["type"] == "action_applied":
                    action_received = True
                    print(f"✓ 动作已应用: {data['sequence']}")
                elif data["type"] == "frame":
                    frame_received = True
                    joints = data["joints"]
                    left_elbow = joints.get("left_elbow", {})
                    angles = left_elbow.get("euler_angles", [0, 0, 0])
                    print(f"✓ 收到帧数据, 左肘角度: [{angles[0]:.3f}, {angles[1]:.3f}, {angles[2]:.3f}]")
                    break
            
            assert action_received, "未收到 action_applied 消息"
            assert frame_received, "未收到 frame 消息"
            print()

            print("测试3: 发送组合键 W-J...")
            await websocket.send(json.dumps({
                "type": "key_sequence",
                "sequence": ["W", "J"]
            }))
            
            for _ in range(10):
                response = await websocket.recv()
                data = json.loads(response)
                if data["type"] == "action_applied":
                    print(f"✓ 组合动作已应用: {data['sequence']}")
                    break
            print()

            print("测试4: 检查帧数据流...")
            frame_count = 0
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < 1.0:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    data = json.loads(response)
                    if data["type"] == "frame":
                        frame_count += 1
                except asyncio.TimeoutError:
                    break
            
            print(f"✓ 1秒内收到 {frame_count} 帧 (预期约60帧)")
            assert frame_count > 30, "帧率过低"
            print()

            print("测试5: 重置皮影姿态...")
            await websocket.send(json.dumps({"type": "reset"}))
            for _ in range(5):
                response = await websocket.recv()
                data = json.loads(response)
                if data["type"] == "reset_complete":
                    print("✓ 重置完成")
                    break
            print()

            print("测试6: 验证旋转矩阵格式...")
            await websocket.send(json.dumps({"type": "get_state"}))
            for _ in range(5):
                response = await websocket.recv()
                data = json.loads(response)
                if data["type"] == "state":
                    joints = data["joints"]
                    for joint_name in ["left_elbow", "right_elbow", "left_knee", "right_knee"]:
                        joint = joints[joint_name]
                        rot_matrix = joint["rotation_matrix"]
                        assert len(rot_matrix) == 3, f"{joint_name} 旋转矩阵行数错误"
                        assert len(rot_matrix[0]) == 3, f"{joint_name} 旋转矩阵列数错误"
                        print(f"  ✓ {joint_name}: 3x3 旋转矩阵格式正确")
                    break
            print()

            print("=" * 60)
            print("所有 WebSocket 集成测试通过!")
            print("=" * 60)
            return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print()


if __name__ == "__main__":
    success = asyncio.run(test_websocket())
    sys.exit(0 if success else 1)
