#!/usr/bin/env python3
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.websocket_server import ShadowPuppetServer


def main():
    parser = argparse.ArgumentParser(
        description="Shadow Puppet Digital Preservation System - Backend Server"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind the server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port number to bind the server (default: 8765)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("皮影戏数字化保存与远程提线演练系统 - 后端服务")
    print("Shadow Puppet Digital Preservation System - Backend")
    print("=" * 60)
    print(f"皮质动力学物理引擎已加载")
    print(f"WebSocket 服务将在 ws://{args.host}:{args.port} 启动")
    print("=" * 60)
    print("按键映射说明:")
    print("  基础移动: W(上) S(下) A(左) D(右) Q(前) E(后)")
    print("  左手控制: U(左肩) J(左肘)")
    print("  右手控制: I(右肩) K(右肘)")
    print("  左腿控制: V(左胯) N(左膝)")
    print("  右腿控制: B(右胯) M(右膝)")
    print("  组合技: W-J  W-K  S-N  S-M  J-K")
    print("  连招技: W-U-J  W-I-K")
    print("=" * 60)
    print("按 Ctrl+C 停止服务")
    print()

    try:
        server = ShadowPuppetServer(host=args.host, port=args.port)
        server.run()
    except KeyboardInterrupt:
        print("\n[INFO] 服务已停止")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] 服务启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
