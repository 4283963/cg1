import * as THREE from 'three';
import { ref } from 'vue';
import type { FrameData } from '../types/shadowPuppet';

interface JointObject3D {
  name: string;
  object: THREE.Object3D;
  mesh: THREE.Mesh;
  targetQuaternion: THREE.Quaternion;
  currentQuaternion: THREE.Quaternion;
  parentName: string | null;
}

let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let animationFrameId: number | null = null;
let lastFpsUpdate = 0;
let frameCountForFps = 0;
const joints: Map<string, JointObject3D> = new Map();
const puppetRoot = new THREE.Group();
let animationSmoothness = 0.12;

const jointHierarchy: Record<string, string | null> = {
  root: null,
  spine: 'root',
  neck: 'spine',
  head: 'neck',
  left_shoulder: 'root',
  left_elbow: 'left_shoulder',
  left_wrist: 'left_elbow',
  left_hand: 'left_wrist',
  right_shoulder: 'root',
  right_elbow: 'right_shoulder',
  right_wrist: 'right_elbow',
  right_hand: 'right_wrist',
  left_hip: 'root',
  left_knee: 'left_hip',
  left_ankle: 'left_knee',
  left_foot: 'left_ankle',
  right_hip: 'root',
  right_knee: 'right_hip',
  right_ankle: 'right_knee',
  right_foot: 'right_ankle'
};

const jointPositions: Record<string, [number, number, number]> = {
  root: [0, 1.6, 0],
  spine: [0, 1.3, 0],
  neck: [0, 1.55, 0],
  head: [0, 1.7, 0],
  left_shoulder: [-0.22, 1.5, 0],
  left_elbow: [-0.45, 1.2, 0],
  left_wrist: [-0.6, 0.9, 0],
  left_hand: [-0.65, 0.85, 0],
  right_shoulder: [0.22, 1.5, 0],
  right_elbow: [0.45, 1.2, 0],
  right_wrist: [0.6, 0.9, 0],
  right_hand: [0.65, 0.85, 0],
  left_hip: [-0.12, 1.0, 0],
  left_knee: [-0.15, 0.55, 0],
  left_ankle: [-0.18, 0.1, 0],
  left_foot: [-0.2, 0, 0.05],
  right_hip: [0.12, 1.0, 0],
  right_knee: [0.15, 0.55, 0],
  right_ankle: [0.18, 0.1, 0],
  right_foot: [0.2, 0, 0.05]
};

const jointDimensions: Record<string, [number, number, number]> = {
  root: [0, 0, 0],
  spine: [0.08, 0.35, 0.02],
  neck: [0.04, 0.12, 0.02],
  head: [0.15, 0.18, 0.02],
  left_shoulder: [0.06, 0.1, 0.02],
  left_elbow: [0.05, 0.08, 0.02],
  left_wrist: [0.04, 0.06, 0.02],
  left_hand: [0.08, 0.12, 0.015],
  right_shoulder: [0.06, 0.1, 0.02],
  right_elbow: [0.05, 0.08, 0.02],
  right_wrist: [0.04, 0.06, 0.02],
  right_hand: [0.08, 0.12, 0.015],
  left_hip: [0.08, 0.12, 0.02],
  left_knee: [0.06, 0.1, 0.02],
  left_ankle: [0.05, 0.08, 0.02],
  left_foot: [0.1, 0.03, 0.15],
  right_hip: [0.08, 0.12, 0.02],
  right_knee: [0.06, 0.1, 0.02],
  right_ankle: [0.05, 0.08, 0.02],
  right_foot: [0.1, 0.03, 0.15]
};

const jointColors: Record<string, number> = {
  root: 0x8B0000,
  spine: 0xA0522D,
  neck: 0xCD853F,
  head: 0xDEB887,
  left_shoulder: 0x8B4513,
  left_elbow: 0xA0522D,
  left_wrist: 0xCD853F,
  left_hand: 0xDEB887,
  right_shoulder: 0x8B4513,
  right_elbow: 0xA0522D,
  right_wrist: 0xCD853F,
  right_hand: 0xDEB887,
  left_hip: 0x8B4513,
  left_knee: 0xA0522D,
  left_ankle: 0xCD853F,
  left_foot: 0x8B4513,
  right_hip: 0x8B4513,
  right_knee: 0xA0522D,
  right_ankle: 0xCD853F,
  right_foot: 0x8B4513
};

export function useShadowPuppetRenderer() {
  const isInitialized = ref(false);
  const frameCount = ref(0);
  const fps = ref(0);

  function createLeatherMaterial(color: number): THREE.MeshStandardMaterial {
    return new THREE.MeshStandardMaterial({
      color: color,
      roughness: 0.7,
      metalness: 0.1,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.95,
      emissive: color,
      emissiveIntensity: 0.1
    });
  }

  function createLineMaterial(): THREE.LineBasicMaterial {
    return new THREE.LineBasicMaterial({
      color: 0xDAA520,
      transparent: true,
      opacity: 0.6
    });
  }

  function getJointDepth(jointName: string): number {
    let depth = 0;
    let current: string | null = jointName;
    while (current) {
      current = jointHierarchy[current];
      depth++;
    }
    return depth;
  }

  function createPuppet() {
    const sortedJoints = Object.keys(jointHierarchy).sort((a, b) => {
      const depthA = getJointDepth(a);
      const depthB = getJointDepth(b);
      return depthA - depthB;
    });

    for (const jointName of sortedJoints) {
      const parentName = jointHierarchy[jointName];
      const pos = jointPositions[jointName];
      const dims = jointDimensions[jointName];
      const color = jointColors[jointName];

      const jointGroup = new THREE.Group();
      jointGroup.name = jointName;
      jointGroup.position.set(pos[0], pos[1], pos[2]);

      if (dims[0] > 0 && dims[1] > 0) {
        const geometry = new THREE.BoxGeometry(dims[0], dims[1], dims[2]);
        const material = createLeatherMaterial(color);
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        jointGroup.add(mesh);

        const edges = new THREE.EdgesGeometry(geometry);
        const edgeLine = new THREE.LineSegments(edges, createLineMaterial());
        mesh.add(edgeLine);

        const jointObj: JointObject3D = {
          name: jointName,
          object: jointGroup,
          mesh: mesh,
          targetQuaternion: new THREE.Quaternion(),
          currentQuaternion: new THREE.Quaternion(),
          parentName: parentName
        };
        joints.set(jointName, jointObj);
      } else {
        const jointObj: JointObject3D = {
          name: jointName,
          object: jointGroup,
          mesh: new THREE.Mesh(),
          targetQuaternion: new THREE.Quaternion(),
          currentQuaternion: new THREE.Quaternion(),
          parentName: parentName
        };
        joints.set(jointName, jointObj);
      }

      if (parentName) {
        const parentJoint = joints.get(parentName);
        if (parentJoint) {
          parentJoint.object.add(jointGroup);
        }
      } else {
        puppetRoot.add(jointGroup);
      }
    }
  }

  function addStringLines() {
    const controlPoints = [
      { joint: 'left_hand', control: new THREE.Vector3(-0.65, 2.5, 0) },
      { joint: 'right_hand', control: new THREE.Vector3(0.65, 2.5, 0) },
      { joint: 'head', control: new THREE.Vector3(0, 2.8, 0) },
      { joint: 'left_foot', control: new THREE.Vector3(-0.2, 2.5, 0.05) },
      { joint: 'right_foot', control: new THREE.Vector3(0.2, 2.5, 0.05) }
    ];

    for (const cp of controlPoints) {
      const jointObj = joints.get(cp.joint);
      if (!jointObj) continue;

      const points = [
        cp.control,
        new THREE.Vector3(0, 0, 0)
      ];
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const material = new THREE.LineBasicMaterial({
        color: 0x666666,
        transparent: true,
        opacity: 0.4
      });
      const line = new THREE.Line(geometry, material);
      line.userData = { jointName: cp.joint, controlPoint: cp.control };
      line.name = `string_${cp.joint}`;
      puppetRoot.add(line);
    }
  }

  function updateStringLines() {
    for (const child of puppetRoot.children) {
      if (child.name.startsWith('string_')) {
        const line = child as THREE.Line;
        const userData = line.userData as { jointName: string; controlPoint: THREE.Vector3 };
        const jointObj = joints.get(userData.jointName);
        if (jointObj) {
          const worldPos = new THREE.Vector3();
          jointObj.object.getWorldPosition(worldPos);
          
          const positions = line.geometry.attributes.position.array as Float32Array;
          positions[0] = userData.controlPoint.x;
          positions[1] = userData.controlPoint.y;
          positions[2] = userData.controlPoint.z;
          positions[3] = worldPos.x;
          positions[4] = worldPos.y;
          positions[5] = worldPos.z;
          line.geometry.attributes.position.needsUpdate = true;
        }
      }
    }
  }

  function matrixToQuaternion(matrix: number[][]): THREE.Quaternion {
    const m = new THREE.Matrix4();
    m.set(
      matrix[0][0], matrix[0][1], matrix[0][2], 0,
      matrix[1][0], matrix[1][1], matrix[1][2], 0,
      matrix[2][0], matrix[2][1], matrix[2][2], 0,
      0, 0, 0, 1
    );
    const q = new THREE.Quaternion();
    q.setFromRotationMatrix(m);
    return q;
  }

  function updateAnimation(deltaTime: number) {
    const lerpFactor = Math.min(animationSmoothness * deltaTime * 60, 1.0);

    for (const jointObj of joints.values()) {
      jointObj.currentQuaternion.slerp(jointObj.targetQuaternion, lerpFactor);
      jointObj.object.quaternion.copy(jointObj.currentQuaternion);
    }

    updateStringLines();
  }

  function animate() {
    animationFrameId = requestAnimationFrame(animate);

    const now = performance.now();
    frameCountForFps++;

    if (now - lastFpsUpdate >= 1000) {
      fps.value = Math.round(frameCountForFps * 1000 / (now - lastFpsUpdate));
      lastFpsUpdate = now;
      frameCountForFps = 0;
    }

    updateAnimation(1 / 60);

    if (renderer && scene && camera) {
      renderer.render(scene, camera);
    }

    frameCount.value++;
  }

  function init(container: HTMLElement) {
    if (isInitialized.value) return;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0f);
    scene.fog = new THREE.FogExp2(0x0a0a0f, 0.05);

    const width = container.clientWidth;
    const height = container.clientHeight;

    camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 100);
    camera.position.set(0, 1.2, 4);
    camera.lookAt(0, 1, 0);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
    scene.add(ambientLight);

    const mainLight = new THREE.DirectionalLight(0xfff5e6, 1.2);
    mainLight.position.set(3, 5, 4);
    mainLight.castShadow = true;
    mainLight.shadow.mapSize.width = 2048;
    mainLight.shadow.mapSize.height = 2048;
    mainLight.shadow.camera.near = 0.5;
    mainLight.shadow.camera.far = 50;
    mainLight.shadow.camera.left = -3;
    mainLight.shadow.camera.right = 3;
    mainLight.shadow.camera.top = 3;
    mainLight.shadow.camera.bottom = -3;
    scene.add(mainLight);

    const fillLight = new THREE.DirectionalLight(0xffd700, 0.4);
    fillLight.position.set(-3, 2, 3);
    scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xff4500, 0.3);
    rimLight.position.set(0, 3, -4);
    scene.add(rimLight);

    const backLight = new THREE.SpotLight(0xff6600, 0.8);
    backLight.position.set(0, 1, -3);
    backLight.angle = Math.PI / 3;
    backLight.penumbra = 0.5;
    scene.add(backLight);

    const projectionPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(8, 5),
      new THREE.MeshStandardMaterial({
        color: 0x1a1520,
        roughness: 0.9,
        metalness: 0.1,
        side: THREE.DoubleSide
      })
    );
    projectionPlane.position.z = -1;
    projectionPlane.receiveShadow = true;
    scene.add(projectionPlane);

    const groundPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(10, 10),
      new THREE.MeshStandardMaterial({
        color: 0x151520,
        roughness: 0.8,
        metalness: 0.2
      })
    );
    groundPlane.rotation.x = -Math.PI / 2;
    groundPlane.position.y = -0.1;
    groundPlane.receiveShadow = true;
    scene.add(groundPlane);

    createPuppet();
    scene.add(puppetRoot);

    addStringLines();

    window.addEventListener('resize', () => handleResize(container));

    isInitialized.value = true;
    animate();

    console.log('Shadow Puppet Renderer initialized');
  }

  function updateJointsFromFrame(frameData: FrameData) {
    if (!frameData.joints) return;

    for (const [jointName, jointData] of Object.entries(frameData.joints)) {
      const jointObj = joints.get(jointName);
      if (!jointObj) continue;

      const targetQ = matrixToQuaternion(jointData.rotation_matrix);
      jointObj.targetQuaternion.copy(targetQ);

      const tension = jointData.tension_force;
      const tensionMag = Math.sqrt(tension[0] ** 2 + tension[1] ** 2 + tension[2] ** 2);
      if (jointObj.mesh.material instanceof THREE.MeshStandardMaterial) {
        jointObj.mesh.material.emissiveIntensity = Math.min(0.1 + tensionMag * 0.002, 0.5);
      }
    }
  }

  function handleResize(container: HTMLElement) {
    if (!camera || !renderer) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }

  function setCameraPosition(x: number, y: number, z: number) {
    if (camera) {
      camera.position.set(x, y, z);
      camera.lookAt(0, 1, 0);
    }
  }

  function setSmoothness(value: number) {
    animationSmoothness = Math.max(0.01, Math.min(1.0, value));
  }

  function resetPuppet() {
    for (const jointObj of joints.values()) {
      jointObj.targetQuaternion.identity();
      jointObj.currentQuaternion.identity();
      jointObj.object.quaternion.identity();
    }
  }

  function getJointAngles(): Record<string, number[]> {
    const result: Record<string, number[]> = {};
    for (const [name, jointObj] of joints) {
      const euler = new THREE.Euler().setFromQuaternion(jointObj.currentQuaternion);
      result[name] = [
        Math.round(euler.x * 180 / Math.PI),
        Math.round(euler.y * 180 / Math.PI),
        Math.round(euler.z * 180 / Math.PI)
      ];
    }
    return result;
  }

  function dispose() {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
    }

    for (const jointObj of joints.values()) {
      if (jointObj.mesh.geometry) {
        jointObj.mesh.geometry.dispose();
      }
      if (jointObj.mesh.material) {
        if (Array.isArray(jointObj.mesh.material)) {
          jointObj.mesh.material.forEach(m => m.dispose());
        } else {
          jointObj.mesh.material.dispose();
        }
      }
    }

    if (renderer) {
      renderer.dispose();
    }

    joints.clear();
    isInitialized.value = false;
    scene = null;
    camera = null;
    renderer = null;
  }

  return {
    isInitialized,
    frameCount,
    fps,
    init,
    dispose,
    updateJointsFromFrame,
    resetPuppet,
    setCameraPosition,
    setSmoothness,
    getJointAngles,
    handleResize
  };
}

