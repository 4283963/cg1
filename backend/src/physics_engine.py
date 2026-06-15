import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import time
import math


@dataclass
class LeatherMaterial:
    young_modulus: float = 1.5e6
    poisson_ratio: float = 0.35
    thickness: float = 0.003
    damping_coefficient: float = 45.0
    mass_per_unit_area: float = 0.8
    air_resistance: float = 0.12
    gravity: float = 9.81


@dataclass
class JointState:
    angle: np.ndarray = field(default_factory=lambda: np.zeros(3))
    angular_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    angular_acceleration: np.ndarray = field(default_factory=lambda: np.zeros(3))
    tension_force: np.ndarray = field(default_factory=lambda: np.zeros(3))
    parent_joint: str = None
    child_joints: List[str] = field(default_factory=list)
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    rest_angle: np.ndarray = field(default_factory=lambda: np.zeros(3))
    joint_limits: Tuple[np.ndarray, np.ndarray] = field(
        default_factory=lambda: (np.array([-np.pi/2, -np.pi/3, -np.pi/4]),
                                 np.array([np.pi/2, np.pi/3, np.pi/4]))
    )


@dataclass
class KeySequenceAction:
    keys: List[str]
    force_magnitude: float
    force_direction: np.ndarray
    target_joint: str
    duration: float = 0.3
    impulse: bool = True


class ShadowPuppetPhysics:
    def __init__(self):
        self.material = LeatherMaterial()
        self.joints: Dict[str, JointState] = {}
        self.joint_dimensions: Dict[str, Tuple[float, float]] = {}
        self.time = 0.0
        self.dt = 0.016
        self._init_puppet_skeleton()
        self._init_key_action_map()

    def _init_puppet_skeleton(self):
        self.joints['root'] = JointState(
            parent_joint=None,
            child_joints=['spine', 'left_shoulder', 'right_shoulder', 'left_hip', 'right_hip'],
            position=np.array([0.0, 1.6, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.zeros(3), np.zeros(3))
        )
        self.joint_dimensions['root'] = (0.0, 0.0)

        self.joints['spine'] = JointState(
            parent_joint='root',
            child_joints=['neck'],
            position=np.array([0.0, 1.3, 0.0]),
            rest_angle=np.array([0.0, 0.0, 0.0]),
            joint_limits=(np.array([-np.pi/6, -np.pi/6, -np.pi/6]),
                         np.array([np.pi/6, np.pi/6, np.pi/6]))
        )
        self.joint_dimensions['spine'] = (0.08, 0.3)

        self.joints['neck'] = JointState(
            parent_joint='spine',
            child_joints=['head'],
            position=np.array([0.0, 1.55, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/4, -np.pi/4, -np.pi/6]),
                         np.array([np.pi/4, np.pi/4, np.pi/6]))
        )
        self.joint_dimensions['neck'] = (0.04, 0.1)

        self.joints['head'] = JointState(
            parent_joint='neck',
            child_joints=[],
            position=np.array([0.0, 1.7, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/6, -np.pi/4, -np.pi/8]),
                         np.array([np.pi/6, np.pi/4, np.pi/8]))
        )
        self.joint_dimensions['head'] = (0.12, 0.15)

        self.joints['left_shoulder'] = JointState(
            parent_joint='root',
            child_joints=['left_elbow'],
            position=np.array([-0.22, 1.5, 0.0]),
            rest_angle=np.array([0.0, 0.0, np.pi/6]),
            joint_limits=(np.array([-np.pi/2, -np.pi/3, -np.pi/3]),
                         np.array([np.pi/2, np.pi/2, np.pi/2]))
        )
        self.joint_dimensions['left_shoulder'] = (0.06, 0.08)

        self.joints['left_elbow'] = JointState(
            parent_joint='left_shoulder',
            child_joints=['left_wrist'],
            position=np.array([-0.45, 1.2, 0.0]),
            rest_angle=np.array([0.0, 0.0, -np.pi/8]),
            joint_limits=(np.array([0.0, -np.pi/2, -np.pi/4]),
                         np.array([np.pi * 0.8, np.pi/3, np.pi/4]))
        )
        self.joint_dimensions['left_elbow'] = (0.05, 0.06)

        self.joints['left_wrist'] = JointState(
            parent_joint='left_elbow',
            child_joints=['left_hand'],
            position=np.array([-0.6, 0.9, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/3, -np.pi/4, -np.pi/6]),
                         np.array([np.pi/3, np.pi/4, np.pi/6]))
        )
        self.joint_dimensions['left_wrist'] = (0.04, 0.05)

        self.joints['left_hand'] = JointState(
            parent_joint='left_wrist',
            child_joints=[],
            position=np.array([-0.65, 0.85, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/6, -np.pi/6, -np.pi/8]),
                         np.array([np.pi/6, np.pi/6, np.pi/8]))
        )
        self.joint_dimensions['left_hand'] = (0.06, 0.1)

        self.joints['right_shoulder'] = JointState(
            parent_joint='root',
            child_joints=['right_elbow'],
            position=np.array([0.22, 1.5, 0.0]),
            rest_angle=np.array([0.0, 0.0, -np.pi/6]),
            joint_limits=(np.array([-np.pi/2, -np.pi/2, -np.pi/2]),
                         np.array([np.pi/2, np.pi/3, np.pi/3]))
        )
        self.joint_dimensions['right_shoulder'] = (0.06, 0.08)

        self.joints['right_elbow'] = JointState(
            parent_joint='right_shoulder',
            child_joints=['right_wrist'],
            position=np.array([0.45, 1.2, 0.0]),
            rest_angle=np.array([0.0, 0.0, np.pi/8]),
            joint_limits=(np.array([0.0, -np.pi/3, -np.pi/4]),
                         np.array([np.pi * 0.8, np.pi/2, np.pi/4]))
        )
        self.joint_dimensions['right_elbow'] = (0.05, 0.06)

        self.joints['right_wrist'] = JointState(
            parent_joint='right_elbow',
            child_joints=['right_hand'],
            position=np.array([0.6, 0.9, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/3, -np.pi/4, -np.pi/6]),
                         np.array([np.pi/3, np.pi/4, np.pi/6]))
        )
        self.joint_dimensions['right_wrist'] = (0.04, 0.05)

        self.joints['right_hand'] = JointState(
            parent_joint='right_wrist',
            child_joints=[],
            position=np.array([0.65, 0.85, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/6, -np.pi/6, -np.pi/8]),
                         np.array([np.pi/6, np.pi/6, np.pi/8]))
        )
        self.joint_dimensions['right_hand'] = (0.06, 0.1)

        self.joints['left_hip'] = JointState(
            parent_joint='root',
            child_joints=['left_knee'],
            position=np.array([-0.12, 1.0, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/3, -np.pi/6, -np.pi/6]),
                         np.array([np.pi/2, np.pi/6, np.pi/6]))
        )
        self.joint_dimensions['left_hip'] = (0.07, 0.1)

        self.joints['left_knee'] = JointState(
            parent_joint='left_hip',
            child_joints=['left_ankle'],
            position=np.array([-0.15, 0.55, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([0.0, -np.pi/6, -np.pi/8]),
                         np.array([np.pi * 0.9, np.pi/6, np.pi/8]))
        )
        self.joint_dimensions['left_knee'] = (0.06, 0.08)

        self.joints['left_ankle'] = JointState(
            parent_joint='left_knee',
            child_joints=['left_foot'],
            position=np.array([-0.18, 0.1, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/4, -np.pi/6, -np.pi/8]),
                         np.array([np.pi/4, np.pi/6, np.pi/8]))
        )
        self.joint_dimensions['left_ankle'] = (0.05, 0.06)

        self.joints['left_foot'] = JointState(
            parent_joint='left_ankle',
            child_joints=[],
            position=np.array([-0.2, 0.0, 0.05]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/6, -np.pi/8, -np.pi/12]),
                         np.array([np.pi/6, np.pi/8, np.pi/12]))
        )
        self.joint_dimensions['left_foot'] = (0.08, 0.12)

        self.joints['right_hip'] = JointState(
            parent_joint='root',
            child_joints=['right_knee'],
            position=np.array([0.12, 1.0, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/3, -np.pi/6, -np.pi/6]),
                         np.array([np.pi/2, np.pi/6, np.pi/6]))
        )
        self.joint_dimensions['right_hip'] = (0.07, 0.1)

        self.joints['right_knee'] = JointState(
            parent_joint='right_hip',
            child_joints=['right_ankle'],
            position=np.array([0.15, 0.55, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([0.0, -np.pi/6, -np.pi/8]),
                         np.array([np.pi * 0.9, np.pi/6, np.pi/8]))
        )
        self.joint_dimensions['right_knee'] = (0.06, 0.08)

        self.joints['right_ankle'] = JointState(
            parent_joint='right_knee',
            child_joints=['right_foot'],
            position=np.array([0.18, 0.1, 0.0]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/4, -np.pi/6, -np.pi/8]),
                         np.array([np.pi/4, np.pi/6, np.pi/8]))
        )
        self.joint_dimensions['right_ankle'] = (0.05, 0.06)

        self.joints['right_foot'] = JointState(
            parent_joint='right_ankle',
            child_joints=[],
            position=np.array([0.2, 0.0, 0.05]),
            rest_angle=np.zeros(3),
            joint_limits=(np.array([-np.pi/6, -np.pi/8, -np.pi/12]),
                         np.array([np.pi/6, np.pi/8, np.pi/12]))
        )
        self.joint_dimensions['right_foot'] = (0.08, 0.12)

    def _init_key_action_map(self):
        self.key_action_map = {
            ('W',): KeySequenceAction(
                keys=['W'], force_magnitude=120.0,
                force_direction=np.array([0.0, 1.0, 0.0]),
                target_joint='spine', duration=0.25, impulse=True
            ),
            ('S',): KeySequenceAction(
                keys=['S'], force_magnitude=100.0,
                force_direction=np.array([0.0, -1.0, 0.0]),
                target_joint='spine', duration=0.25, impulse=True
            ),
            ('A',): KeySequenceAction(
                keys=['A'], force_magnitude=90.0,
                force_direction=np.array([-1.0, 0.0, 0.0]),
                target_joint='spine', duration=0.2, impulse=True
            ),
            ('D',): KeySequenceAction(
                keys=['D'], force_magnitude=90.0,
                force_direction=np.array([1.0, 0.0, 0.0]),
                target_joint='spine', duration=0.2, impulse=True
            ),
            ('Q',): KeySequenceAction(
                keys=['Q'], force_magnitude=80.0,
                force_direction=np.array([0.0, 0.0, 1.0]),
                target_joint='spine', duration=0.2, impulse=True
            ),
            ('E',): KeySequenceAction(
                keys=['E'], force_magnitude=80.0,
                force_direction=np.array([0.0, 0.0, -1.0]),
                target_joint='spine', duration=0.2, impulse=True
            ),
            ('J',): KeySequenceAction(
                keys=['J'], force_magnitude=150.0,
                force_direction=np.array([-1.0, 1.0, 0.3]),
                target_joint='left_elbow', duration=0.3, impulse=True
            ),
            ('K',): KeySequenceAction(
                keys=['K'], force_magnitude=150.0,
                force_direction=np.array([1.0, 1.0, 0.3]),
                target_joint='right_elbow', duration=0.3, impulse=True
            ),
            ('U',): KeySequenceAction(
                keys=['U'], force_magnitude=130.0,
                force_direction=np.array([-1.0, 1.2, 0.0]),
                target_joint='left_shoulder', duration=0.35, impulse=True
            ),
            ('I',): KeySequenceAction(
                keys=['I'], force_magnitude=130.0,
                force_direction=np.array([1.0, 1.2, 0.0]),
                target_joint='right_shoulder', duration=0.35, impulse=True
            ),
            ('N',): KeySequenceAction(
                keys=['N'], force_magnitude=140.0,
                force_direction=np.array([-0.5, -1.0, 0.2]),
                target_joint='left_knee', duration=0.3, impulse=True
            ),
            ('M',): KeySequenceAction(
                keys=['M'], force_magnitude=140.0,
                force_direction=np.array([0.5, -1.0, 0.2]),
                target_joint='right_knee', duration=0.3, impulse=True
            ),
            ('V',): KeySequenceAction(
                keys=['V'], force_magnitude=120.0,
                force_direction=np.array([-0.3, -1.2, 0.1]),
                target_joint='left_hip', duration=0.35, impulse=True
            ),
            ('B',): KeySequenceAction(
                keys=['B'], force_magnitude=120.0,
                force_direction=np.array([0.3, -1.2, 0.1]),
                target_joint='right_hip', duration=0.35, impulse=True
            ),
            ('W', 'J'): KeySequenceAction(
                keys=['W', 'J'], force_magnitude=200.0,
                force_direction=np.array([-0.8, 1.5, 0.4]),
                target_joint='left_elbow', duration=0.4, impulse=True
            ),
            ('W', 'K'): KeySequenceAction(
                keys=['W', 'K'], force_magnitude=200.0,
                force_direction=np.array([0.8, 1.5, 0.4]),
                target_joint='right_elbow', duration=0.4, impulse=True
            ),
            ('S', 'N'): KeySequenceAction(
                keys=['S', 'N'], force_magnitude=180.0,
                force_direction=np.array([-0.5, -1.5, 0.3]),
                target_joint='left_knee', duration=0.4, impulse=True
            ),
            ('S', 'M'): KeySequenceAction(
                keys=['S', 'M'], force_magnitude=180.0,
                force_direction=np.array([0.5, -1.5, 0.3]),
                target_joint='right_knee', duration=0.4, impulse=True
            ),
            ('J', 'K'): KeySequenceAction(
                keys=['J', 'K'], force_magnitude=160.0,
                force_direction=np.array([0.0, 1.8, 0.5]),
                target_joint='spine', duration=0.35, impulse=True
            ),
            ('W', 'U', 'J'): KeySequenceAction(
                keys=['W', 'U', 'J'], force_magnitude=250.0,
                force_direction=np.array([-1.0, 2.0, 0.6]),
                target_joint='left_shoulder', duration=0.5, impulse=True
            ),
            ('W', 'I', 'K'): KeySequenceAction(
                keys=['W', 'I', 'K'], force_magnitude=250.0,
                force_direction=np.array([1.0, 2.0, 0.6]),
                target_joint='right_shoulder', duration=0.5, impulse=True
            ),
        }
        self.pending_actions: List[Tuple[KeySequenceAction, float]] = []

    def apply_key_sequence(self, key_sequence: List[str]) -> bool:
        key_tuple = tuple(key_sequence)
        if key_tuple in self.key_action_map:
            action = self.key_action_map[key_tuple]
            self.pending_actions.append((action, self.time))
            return True
        return False

    def _calculate_joint_inertia(self, joint_name: str) -> float:
        width, length = self.joint_dimensions.get(joint_name, (0.05, 0.1))
        mass = self.material.mass_per_unit_area * width * length
        inertia = (1/12) * mass * (width**2 + length**2)
        return max(inertia, 1e-4)

    def _calculate_spring_torque(self, joint: JointState, joint_name: str) -> np.ndarray:
        displacement = joint.angle - joint.rest_angle
        width, length = self.joint_dimensions.get(joint_name, (0.05, 0.1))
        length = max(length, 0.01)
        width = max(width, 0.01)
        cross_sectional_area = width * self.material.thickness
        spring_constant = (self.material.young_modulus * cross_sectional_area) / length
        return -spring_constant * displacement

    def _calculate_damping_torque(self, joint: JointState) -> np.ndarray:
        return -self.material.damping_coefficient * joint.angular_velocity

    def _calculate_gravity_torque(self, joint: JointState, joint_name: str) -> np.ndarray:
        if joint.parent_joint is None:
            return np.zeros(3)
        width, length = self.joint_dimensions.get(joint_name, (0.05, 0.1))
        mass = self.material.mass_per_unit_area * width * length
        parent_pos = self.joints[joint.parent_joint].position
        joint_to_cm = (joint.position - parent_pos) * 0.5
        gravity_force = np.array([0.0, -mass * self.material.gravity, 0.0])
        torque = np.cross(joint_to_cm, gravity_force)
        return torque

    def _calculate_air_resistance_torque(self, joint: JointState) -> np.ndarray:
        return -self.material.air_resistance * np.sign(joint.angular_velocity) * (joint.angular_velocity ** 2)

    def _apply_tension_force(self, joint: JointState, force: np.ndarray, joint_name: str) -> np.ndarray:
        if joint.parent_joint is None:
            return np.zeros(3)
        parent_pos = self.joints[joint.parent_joint].position
        lever_arm = joint.position - parent_pos
        if np.linalg.norm(lever_arm) > 0:
            lever_arm = lever_arm / np.linalg.norm(lever_arm)
        torque = np.cross(lever_arm, force)
        return torque

    def _enforce_joint_limits(self, joint: JointState) -> None:
        min_limits, max_limits = joint.joint_limits
        for i in range(3):
            if joint.angle[i] < min_limits[i]:
                joint.angle[i] = min_limits[i]
                if joint.angular_velocity[i] < 0:
                    joint.angular_velocity[i] *= -0.3
            elif joint.angle[i] > max_limits[i]:
                joint.angle[i] = max_limits[i]
                if joint.angular_velocity[i] > 0:
                    joint.angular_velocity[i] *= -0.3

    def step(self, dt: float = None) -> Dict[str, Dict]:
        if dt is None:
            dt = self.dt
        self.time += dt

        current_actions = []
        still_pending = []
        for action, start_time in self.pending_actions:
            elapsed = self.time - start_time
            if elapsed < action.duration:
                current_actions.append((action, elapsed))
                still_pending.append((action, start_time))
        self.pending_actions = still_pending

        tension_forces = {}
        for joint_name in self.joints:
            tension_forces[joint_name] = np.zeros(3)

        for action, elapsed in current_actions:
            t = elapsed / action.duration
            if action.impulse:
                force_scale = math.exp(-(t - 0.3)**2 / 0.05) * 4.0
            else:
                force_scale = 1.0 - t
            force = action.force_direction * action.force_magnitude * force_scale
            tension_forces[action.target_joint] += force

        for joint_name, joint in self.joints.items():
            inertia = self._calculate_joint_inertia(joint_name)

            spring_torque = self._calculate_spring_torque(joint, joint_name)
            damping_torque = self._calculate_damping_torque(joint)
            gravity_torque = self._calculate_gravity_torque(joint, joint_name)
            air_resistance_torque = self._calculate_air_resistance_torque(joint)
            tension_torque = self._apply_tension_force(joint, tension_forces[joint_name], joint_name)

            total_torque = spring_torque + damping_torque + gravity_torque + \
                          air_resistance_torque + tension_torque

            joint.angular_acceleration = total_torque / inertia

            joint.angular_velocity += joint.angular_acceleration * dt

            max_vel = 8.0
            vel_norm = np.linalg.norm(joint.angular_velocity)
            if vel_norm > max_vel:
                joint.angular_velocity = joint.angular_velocity / vel_norm * max_vel

            joint.angle += joint.angular_velocity * dt

            self._enforce_joint_limits(joint)

            joint.tension_force = tension_forces[joint_name].copy()

        return self._get_joint_rotations()

    def _euler_to_rotation_matrix(self, euler_angles: np.ndarray) -> List[List[float]]:
        rx, ry, rz = euler_angles

        Rx = np.array([
            [1, 0, 0],
            [0, math.cos(rx), -math.sin(rx)],
            [0, math.sin(rx), math.cos(rx)]
        ])

        Ry = np.array([
            [math.cos(ry), 0, math.sin(ry)],
            [0, 1, 0],
            [-math.sin(ry), 0, math.cos(ry)]
        ])

        Rz = np.array([
            [math.cos(rz), -math.sin(rz), 0],
            [math.sin(rz), math.cos(rz), 0],
            [0, 0, 1]
        ])

        R = Rz @ Ry @ Rx
        return R.tolist()

    def _get_joint_rotations(self) -> Dict[str, Dict]:
        result = {}
        for joint_name, joint in self.joints.items():
            rotation_matrix = self._euler_to_rotation_matrix(joint.angle)
            result[joint_name] = {
                'rotation_matrix': rotation_matrix,
                'euler_angles': joint.angle.tolist(),
                'angular_velocity': joint.angular_velocity.tolist(),
                'tension_force': joint.tension_force.tolist(),
                'position': joint.position.tolist()
            }
        return result

    def reset(self) -> None:
        self.time = 0.0
        self.pending_actions = []
        for joint in self.joints.values():
            joint.angle = joint.rest_angle.copy()
            joint.angular_velocity = np.zeros(3)
            joint.angular_acceleration = np.zeros(3)
            joint.tension_force = np.zeros(3)

    def simulate(self, key_sequences: List[List[str]], duration: float) -> List[Dict]:
        self.reset()
        frame_count = int(duration / self.dt)
        results = []

        seq_idx = 0
        seq_time = 0.0
        seq_interval = 0.15

        for frame in range(frame_count):
            seq_time += self.dt
            if seq_idx < len(key_sequences) and seq_time >= seq_interval:
                self.apply_key_sequence(key_sequences[seq_idx])
                seq_idx += 1
                seq_time = 0.0

            frame_data = self.step()
            results.append({
                'timestamp': self.time,
                'frame': frame,
                'joints': frame_data
            })

        return results
