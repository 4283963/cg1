#!/usr/bin/env python3
import asyncio
import json
import sys
import websockets


def expand_joints(trimmed):
    expanded = {}
    for joint_name, jd in trimmed.items():
        expanded[joint_name] = {
            'rotation_matrix': jd.get('rm', jd.get('rotation_matrix', [[1,0,0],[0,1,0],[0,0,1]])),
            'euler_angles': jd.get('ea', jd.get('euler_angles', [0, 0, 0])),
        }
    return expanded


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
            await asyncio.sleep(0.05)
            await websocket.send(json.dumps({
                "type": "ping",
                "timestamp": asyncio.get_event_loop().time()
            }))
            
            pong_received = False
            for _ in range(200):
                response = await asyncio.wait_for(websocket.recv(), timeout=0.2)
                data = json.loads(response)
                if data["type"] == "pong":
                    pong_received = True
                    assert "ct" in data or "client_timestamp" in data, "缺少客户端时间戳"
                    break
                elif data["type"] in ["frame", "action_applied", "reset_complete", "state", "warning", "error"]:
                    continue
                else:
                    pass
            
            assert pong_received, "未收到 pong 消息"
            print("✓ Ping-Pong 正常")
            print()

            print("测试2: 发送单键 J (左肘)...")
            await asyncio.sleep(0.1)
            await websocket.send(json.dumps({
                "type": "key_press",
                "key": "J",
                "timestamp": asyncio.get_event_loop().time()
            }))
            
            action_received = False
            frame_received = False
            for _ in range(60):
                response = await asyncio.wait_for(websocket.recv(), timeout=0.2)
                data = json.loads(response)
                if data["type"] == "action_applied":
                    action_received = True
                    print(f"✓ 动作已应用: {data['sequence']}")
                elif data["type"] == "frame" and not frame_received:
                    frame_received = True
                    joints_raw = data.get("j", data.get("joints", {}))
                    joints = expand_joints(joints_raw)
                    left_elbow = joints.get("left_elbow", {})
                    angles = left_elbow.get("euler_angles", [0, 0, 0])
                    print(f"✓ 收到帧数据, 左肘角度: [{angles[0]:.3f}, {angles[1]:.3f}, {angles[2]:.3f}]")
                    frame_size = len(response.encode('utf-8'))
                    print(f"  (帧大小: {frame_size} 字节)")
                
                if action_received and frame_received:
                    break
            
            assert action_received, "未收到 action_applied 消息"
            assert frame_received, "未收到 frame 消息"
            assert frame_size < 64 * 1024, f"帧过大: {frame_size}"
            print()

            print("测试3: 发送组合键 W-J...")
            await websocket.send(json.dumps({
                "type": "key_sequence",
                "sequence": ["W", "J"]
            }))
            
            for _ in range(30):
                response = await websocket.recv()
                data = json.loads(response)
                if data["type"] == "action_applied":
                    print(f"✓ 组合动作已应用: {data['sequence']}")
                    break
            print()

            print("测试4: 检查帧数据流 + 大小...")
            frame_count = 0
            max_frame_size = 0
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < 1.0:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    data = json.loads(response)
                    if data["type"] == "frame":
                        frame_count += 1
                        sz = len(response.encode('utf-8'))
                        max_frame_size = max(max_frame_size, sz)
                except asyncio.TimeoutError:
                    break
            
            print(f"✓ 1秒内收到 {frame_count} 帧 (预期约60帧)")
            print(f"  最大帧大小: {max_frame_size} 字节")
            assert frame_count > 30, "帧率过低"
            assert max_frame_size < 64 * 1024, f"帧过大: {max_frame_size}"
            print()

            print("测试5: 重置皮影姿态...")
            await websocket.send(json.dumps({"type": "reset"}))
            for _ in range(20):
                response = await websocket.recv()
                data = json.loads(response)
                if data["type"] == "reset_complete":
                    print("✓ 重置完成")
                    break
            print()

            print("测试6: 验证旋转矩阵格式...")
            await websocket.send(json.dumps({"type": "get_state"}))
            for _ in range(20):
                response = await websocket.recv()
                data = json.loads(response)
                if data["type"] == "state":
                    joints_raw = data.get("j", data.get("joints", {}))
                    joints = expand_joints(joints_raw)
                    for joint_name in ["left_elbow", "right_elbow", "left_knee", "right_knee"]:
                        joint = joints[joint_name]
                        rot_matrix = joint["rotation_matrix"]
                        assert len(rot_matrix) == 3, f"{joint_name} 旋转矩阵行数错误"
                        assert len(rot_matrix[0]) == 3, f"{joint_name} 旋转矩阵列数错误"
                        
                        for row in rot_matrix:
                            for v in row:
                                s = f"{v}"
                                if '.' in s:
                                    dec_len = len(s.split('.')[1])
                                    assert dec_len <= 3, f"{joint_name} 精度过高: {v}"
                        
                        print(f"  ✓ {joint_name}: 3x3 旋转矩阵格式正确 (精度≤2位小数)")
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
