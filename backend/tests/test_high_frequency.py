#!/usr/bin/env python3
import asyncio
import json
import sys
import time
import websockets


async def test_high_frequency():
    print("=" * 70)
    print("高频连击稳定性压力测试")
    print("=" * 70)
    print()

    uri = "ws://localhost:8765"
    print(f"连接到: {uri}")
    
    try:
        async with websockets.connect(uri, max_size=None) as websocket:
            print("✓ WebSocket 连接成功")
            print()

            print("测试1: 单帧数据包大小检查 + 精度...")
            await asyncio.sleep(0.2)
            
            msg_count = 0
            max_size = 0
            max_decimal_len = 0
            start_time = time.time()
            while time.time() - start_time < 1.5 and msg_count < 100:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    data = json.loads(response)
                    if data["type"] == "frame":
                        size = len(response.encode('utf-8'))
                        max_size = max(max_size, size)
                        
                        joints = data.get("j", {})
                        for joint_name, joint in joints.items():
                            rm = joint.get("rm", [])
                            for row in rm:
                                for v in row:
                                    s = f"{v}"
                                    if '.' in s:
                                        dec_len = len(s.split('.')[1])
                                        max_decimal_len = max(max_decimal_len, dec_len)
                        
                        msg_count += 1
                except asyncio.TimeoutError:
                    break
            
            print(f"  帧数: {msg_count}, 最大帧大小: {max_size} 字节")
            print(f"  最大小数位数: {max_decimal_len}")
            assert max_size < 64 * 1024, f"帧过大: {max_size}"
            assert max_decimal_len <= 3, f"精度超标: {max_decimal_len}"
            print("✓ 测试1通过")
            print()

            print("测试2: 高频疯狂连击 (3秒内发 500 次键)...")
            rapid_start = time.time()
            keys = ['J', 'K', 'W', 'S', 'A', 'D', 'U', 'I']
            sent_count = 0
            for i in range(500):
                key = keys[i % len(keys)]
                key_msg = json.dumps({
                    "type": "key_press",
                    "key": key,
                    "timestamp": time.time()
                })
                try:
                    await websocket.send(key_msg)
                    sent_count += 1
                except Exception as e:
                    print(f"  发送失败 #{i}: {e}")
                    break
            
            rapid_elapsed = time.time() - rapid_start
            print(f"  发送了 {sent_count} 条消息用时 {rapid_elapsed:.3f}s")
            print("✓ 测试2发送完成")
            print()

            print("测试3: 接收数据流稳定性 - 持续 5 秒...")
            frame_count = 0
            dropped_count = 0
            error_count = 0
            max_frame_size = 0
            disconnect_detected = False
            
            start_time = time.time()
            while time.time() - start_time < 5.0:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                    data = json.loads(response)
                    frame_size = len(response.encode('utf-8'))
                    max_frame_size = max(max_frame_size, frame_size)
                    
                    if data["type"] == "frame":
                        frame_count += 1
                        if "df" in data:
                            dropped_count = data["df"]
                                    
                except websockets.exceptions.ConnectionClosed:
                    disconnect_detected = True
                    break
                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    error_count += 1
            
            print(f"  收到帧数: {frame_count}")
            print(f"  最大帧大小: {max_frame_size} 字节")
            print(f"  服务端丢帧数: {dropped_count}")
            print(f"  解析错误数: {error_count}")
            print(f"  连接断开: {'是' if disconnect_detected else '否'}")
            
            assert not disconnect_detected, "连接在高频连击中断开了!"
            assert max_frame_size < 64 * 1024, f"帧大小超出限制!"
            assert frame_count > 100, f"帧率过低: {frame_count} in 5s"
            print("✓ 测试3通过")
            print()

            print("测试4: 连接仍然存活 (ping/pong)...")
            await websocket.send(json.dumps({"type": "ping"}))
            pong_ok = False
            for _ in range(20):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                    data = json.loads(response)
                    if data["type"] == "pong":
                        pong_ok = True
                        break
                except Exception:
                    continue
            assert pong_ok, "没有收到pong"
            print("✓ 测试4通过")
            print()

            print("=" * 70)
            print("所有高频连击压力测试通过! 系统稳定!")
            print("=" * 70)
            return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_high_frequency())
    sys.exit(0 if success else 1)
