#!/usr/bin/env python3
import asyncio
import json
import sys
import time
import websockets


async def test_heat_feature():
    print("=" * 70)
    print("灯光烤炙功能测试")
    print("=" * 70)
    print()

    uri = "ws://localhost:8765"
    print(f"连接到: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket 连接成功")
            print()

            print("测试1: 验证帧数据包含 heat 字段...")
            await asyncio.sleep(0.2)
            
            heat_received = False
            for _ in range(30):
                response = await asyncio.wait_for(websocket.recv(), timeout=0.2)
                data = json.loads(response)
                if data["type"] == "frame":
                    if "h" in data:
                        heat = data["h"]
                        print(f"  Heat字段: t={heat.get('t', 0)}s, hl={heat.get('hl', 0):.3f}, s={heat.get('s', 0):.3f}, on={heat.get('on', True)}")
                        print(f"  字段完整 ✓")
                        heat_received = True
                    break
            
            assert heat_received, "未收到heat字段"
            print("✓ 测试1通过")
            print()

            print("测试2: 等待3秒，观察热量和变软系数上升...")
            start_softness = 0
            end_softness = 0
            start_time = time.time()
            frame_count = 0
            
            while time.time() - start_time < 3.0:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.2)
                    data = json.loads(response)
                    if data["type"] == "frame" and "h" in data:
                        heat = data["h"]
                        if frame_count == 0:
                            start_softness = heat.get("s", 0)
                        frame_count += 1
                        end_softness = heat.get("s", 0)
                except asyncio.TimeoutError:
                    break
            
            print(f"  初始变软系数: {start_softness:.3f}")
            print(f"  3秒后变软系数: {end_softness:.3f}")
            print(f"  收帧数: {frame_count}")
            
            assert end_softness > start_softness, f"变软系数没有上升: {start_softness} -> {end_softness}"
            print(f"✓ 测试2通过 (变软系数上升了 {(end_softness - start_softness) * 100:.1f}%)")
            print()

            print("测试3: 发送 heat_on=false 暂停加热...")
            await websocket.send(json.dumps({
                "type": "heat_on",
                "on": False
            }))
            
            await asyncio.sleep(0.2)
            paused_level = 0
            for _ in range(20):
                response = await asyncio.wait_for(websocket.recv(), timeout=0.2)
                data = json.loads(response)
                if data["type"] == "frame" and "h" in data:
                    heat = data["h"]
                    if heat.get("on") == False:
                        paused_level = heat.get("hl", 0)
                        print(f"  已暂停, 热量级别: {paused_level:.3f}")
                        break
            
            await asyncio.sleep(1.5)
            for _ in range(20):
                response = await asyncio.wait_for(websocket.recv(), timeout=0.2)
                data = json.loads(response)
                if data["type"] == "frame" and "h" in data:
                    heat = data["h"]
                    cooled_level = heat.get("hl", 0)
                    print(f"  1.5秒后, 热量级别: {cooled_level:.3f}")
                    assert cooled_level < paused_level, f"冷却时热量没有下降: {paused_level} -> {cooled_level}"
                    break
            
            print("✓ 测试3通过 (暂停后冷却正常)")
            print()

            print("测试4: 手动设置热量级别 0.8...")
            await websocket.send(json.dumps({
                "type": "heat_level",
                "level": 0.8
            }))
            
            await asyncio.sleep(0.1)
            level_ok = False
            heat_ack_received = False
            for _ in range(200):
                response = await asyncio.wait_for(websocket.recv(), timeout=0.2)
                data = json.loads(response)
                if data["type"] == "heat_ack":
                    print(f"  收到 heat_ack: {data}")
                    heat_ack_received = True
                if data["type"] == "frame" and "h" in data:
                    heat = data["h"]
                    lvl = heat.get("hl", 0)
                    sft = heat.get("s", 0)
                    if heat_ack_received:
                        print(f"  热量: {lvl:.3f}, 变软: {sft:.3f}, on={heat.get('on', False)}")
                    if heat_ack_received and abs(lvl - 0.8) < 0.1:
                        level_ok = True
                        break
            
            assert heat_ack_received, "未收到 heat_ack"
            assert level_ok, "手动设置热量失败"
            print("✓ 测试4通过")
            print()

            print("测试5: 重置热量...")
            await websocket.send(json.dumps({"type": "heat_reset"}))
            
            await asyncio.sleep(0.3)
            reset_ok = False
            for _ in range(20):
                response = await asyncio.wait_for(websocket.recv(), timeout=0.2)
                data = json.loads(response)
                if data["type"] == "frame" and "h" in data:
                    heat = data["h"]
                    if heat.get("hl", 1) < 0.01 and heat.get("s", 1) < 0.01:
                        print(f"  重置后: 热量={heat.get('hl', 0):.3f}, 变软={heat.get('s', 0):.3f}")
                        reset_ok = True
                        break
            
            assert reset_ok, "重置热量失败"
            print("✓ 测试5通过")
            print()

            print("测试6: 验证浮点数精度...")
            await websocket.send(json.dumps({"type": "heat_level", "level": 0.5}))
            await asyncio.sleep(0.5)
            
            for _ in range(20):
                response = await asyncio.wait_for(websocket.recv(), timeout=0.2)
                data = json.loads(response)
                if data["type"] == "frame" and "h" in data:
                    heat = data["h"]
                    for key in ['t', 'hl', 's']:
                        if key in heat:
                            val = heat[key]
                            s = f"{val}"
                            if '.' in s:
                                dec_len = len(s.split('.')[1])
                                print(f"  {key} = {val} (小数位: {dec_len})")
                                assert dec_len <= 3, f"精度超标: {key}={val}"
                    break
            
            print("✓ 测试6通过 (精度≤3位小数)")
            print()

            print("=" * 70)
            print("所有灯光烤炙功能测试通过!")
            print("=" * 70)
            return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_heat_feature())
    sys.exit(0 if success else 1)
