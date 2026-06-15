#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from src.physics_engine import ShadowPuppetPhysics, LeatherMaterial


def test_physics_engine_initialization():
    print("测试1: 物理引擎初始化...")
    physics = ShadowPuppetPhysics()
    assert physics is not None
    assert len(physics.joints) == 20
    assert isinstance(physics.material, LeatherMaterial)
    print("  ✓ 物理引擎初始化成功，关节数量:", len(physics.joints))


def test_skeleton_structure():
    print("测试2: 骨骼结构检查...")
    physics = ShadowPuppetPhysics()

    required_joints = ['root', 'spine', 'neck', 'head',
                       'left_shoulder', 'left_elbow', 'left_wrist', 'left_hand',
                       'right_shoulder', 'right_elbow', 'right_wrist', 'right_hand',
                       'left_hip', 'left_knee', 'left_ankle', 'left_foot',
                       'right_hip', 'right_knee', 'right_ankle', 'right_foot']

    for joint_name in required_joints:
        assert joint_name in physics.joints, f"缺少关节: {joint_name}"
    print("  ✓ 所有20个关节都存在")

    root = physics.joints['root']
    assert root.parent_joint is None
    assert 'spine' in root.child_joints
    print("  ✓ 根关节结构正确")

    left_elbow = physics.joints['left_elbow']
    assert left_elbow.parent_joint == 'left_shoulder'
    assert 'left_wrist' in left_elbow.child_joints
    print("  ✓ 关节父子关系正确")


def test_key_sequence_mapping():
    print("测试3: 按键序列映射...")
    physics = ShadowPuppetPhysics()

    test_sequences = [
        (['W'], True),
        (['J'], True),
        (['K'], True),
        (['W', 'J'], True),
        (['W', 'K'], True),
        (['W', 'U', 'J'], True),
        (['X'], False),
        (['W', 'X'], False),
    ]

    for seq, should_work in test_sequences:
        result = physics.apply_key_sequence(seq)
        assert result == should_work, f"序列 {seq} 预期 {should_work} 但得到 {result}"
    print("  ✓ 所有按键序列映射正确")


def test_physics_simulation():
    print("测试4: 物理模拟...")
    physics = ShadowPuppetPhysics()

    initial_left_elbow = physics.joints['left_elbow'].angle.copy()

    physics.apply_key_sequence(['J'])

    for _ in range(10):
        data = physics.step()

    final_left_elbow = np.array(data['left_elbow']['euler_angles'])

    assert not np.allclose(initial_left_elbow, final_left_elbow), \
        "施加力后关节角度应该变化"
    print("  ✓ 物理模拟运行正常，关节角度随拉力变化")

    assert 'left_elbow' in data
    assert 'rotation_matrix' in data['left_elbow']
    assert len(data['left_elbow']['rotation_matrix']) == 3
    assert len(data['left_elbow']['rotation_matrix'][0]) == 3
    print("  ✓ 旋转矩阵格式正确 (3x3)")


def test_joint_limits():
    print("测试5: 关节限制...")
    physics = ShadowPuppetPhysics()

    left_elbow = physics.joints['left_elbow']
    min_limits, max_limits = left_elbow.joint_limits

    left_elbow.angle = np.array([-10.0, 0.0, 0.0])
    left_elbow.angular_velocity = np.array([-5.0, 0.0, 0.0])
    physics._enforce_joint_limits(left_elbow)

    assert left_elbow.angle[0] >= min_limits[0]
    assert left_elbow.angular_velocity[0] >= 0
    print("  ✓ 关节限制正常工作")


def test_batch_simulation():
    print("测试6: 批量模拟...")
    physics = ShadowPuppetPhysics()

    sequences = [['W'], ['J'], ['W', 'J']]
    results = physics.simulate(sequences, duration=1.0)

    assert len(results) > 0
    assert 'timestamp' in results[0]
    assert 'joints' in results[0]
    print(f"  ✓ 批量模拟完成，生成 {len(results)} 帧数据")


def test_rotation_matrix():
    print("测试7: 旋转矩阵转换...")
    physics = ShadowPuppetPhysics()

    test_angles = np.array([np.pi/4, np.pi/6, np.pi/3])
    R = physics._euler_to_rotation_matrix(test_angles)

    R_np = np.array(R)
    R_times_RT = R_np @ R_np.T
    assert np.allclose(R_times_RT, np.eye(3), atol=1e-2), f"旋转矩阵应该是正交的 (误差={np.max(np.abs(R_times_RT - np.eye(3)))})"
    assert np.isclose(np.linalg.det(R_np), 1.0, atol=1e-2), f"旋转矩阵行列式应为1 (实际={np.linalg.det(R_np)})"
    print("  ✓ 旋转矩阵数学性质正确 (序列化精度已截断)")


def test_damping_and_spring():
    print("测试8: 弹簧阻尼系统...")
    physics = ShadowPuppetPhysics()

    joint = physics.joints['left_elbow']
    joint.angle = np.array([0.5, 0.0, 0.0])
    joint.angular_velocity = np.zeros(3)

    spring_torque = physics._calculate_spring_torque(joint, 'left_elbow')
    assert spring_torque[0] < 0, "弹簧力矩应该与位移方向相反"
    print("  ✓ 弹簧恢复力正常")

    joint.angular_velocity = np.array([1.0, 0.0, 0.0])
    damping_torque = physics._calculate_damping_torque(joint)
    assert damping_torque[0] < 0, "阻尼力矩应该与速度方向相反"
    print("  ✓ 阻尼力正常")


def run_all_tests():
    print("=" * 60)
    print("皮影戏物理引擎单元测试")
    print("=" * 60)
    print()

    tests = [
        test_physics_engine_initialization,
        test_skeleton_structure,
        test_key_sequence_mapping,
        test_physics_simulation,
        test_joint_limits,
        test_batch_simulation,
        test_rotation_matrix,
        test_damping_and_spring,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__} 失败: {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
