import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { Frame, Scenario } from "./types";

interface Props { frame?: Frame; frames: Frame[]; scenario?: Scenario; }

function mulberry32(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let value = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    value = (value + Math.imul(value ^ (value >>> 7), 61 | value)) ^ value;
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function box(size: [number, number, number], color: number, roughness = .75) {
  const material = new THREE.MeshStandardMaterial({ color, roughness, metalness: .12 });
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
  mesh.castShadow = true; mesh.receiveShadow = true;
  return mesh;
}

function createRobot() {
  const group = new THREE.Group(); group.name = "robot";
  const base = box([7, 2.2, 5], 0xd9ff62, .42); base.position.y = 2; group.add(base);
  const dark = new THREE.MeshStandardMaterial({ color: 0x141817, roughness: .65 });
  const wheels: THREE.Mesh[] = [];
  for (const side of [-1, 1]) {
    const wheel = new THREE.Mesh(new THREE.CylinderGeometry(1.35, 1.35, .9, 20), dark);
    wheel.rotation.z = Math.PI / 2; wheel.position.set(0, 1.35, side * 2.8); wheel.castShadow = true;
    wheels.push(wheel); group.add(wheel);
  }
  const mast = box([1.5, 7, 1.5], 0x343c3b, .5); mast.position.set(-1, 6, 0); group.add(mast);
  const shoulder = new THREE.Group(); shoulder.position.set(-1, 9, 0); group.add(shoulder);
  const upper = box([5.5, 1.1, 1.1], 0xaac942, .4); upper.position.x = 2.4; upper.rotation.z = -.35; shoulder.add(upper);
  const elbow = new THREE.Group(); elbow.position.set(5, 0, 0); shoulder.add(elbow);
  const forearm = box([4.4, .9, .9], 0xbfdc54, .4); forearm.position.set(2.1, 0, 0); elbow.add(forearm);
  const sensor = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.1, .65, 24), new THREE.MeshStandardMaterial({ color: 0x202827, emissive: 0x27493e, emissiveIntensity: .7 }));
  sensor.position.set(1.8, 4.1, 0); group.add(sensor);
  group.userData.wheels = wheels; group.userData.shoulder = shoulder; group.userData.elbow = elbow;
  group.scale.setScalar(.3);
  return group;
}

export default function WorldView3D({ frame, frames, scenario }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef(frame);
  const trailRef = useRef(frames);
  useEffect(() => { frameRef.current = frame; trailRef.current = frames; }, [frame, frames]);

  useEffect(() => {
    if (!mountRef.current || !scenario) return;
    const mount = mountRef.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0e0e); scene.fog = new THREE.FogExp2(0x0b0e0e, .009);
    const camera = new THREE.PerspectiveCamera(44, 1, .1, 400); camera.position.set(112, 92, 118);
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement); controls.target.set(50, 0, 48); controls.enableDamping = true; controls.maxPolarAngle = Math.PI * .48; controls.minDistance = 35; controls.maxDistance = 240;

    scene.add(new THREE.HemisphereLight(0xbdd4cf, 0x18201e, 1.7));
    const key = new THREE.DirectionalLight(0xeaffd3, 3.2); key.position.set(35, 90, 45); key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.camera.left = -90; key.shadow.camera.right = 90; key.shadow.camera.top = 90; key.shadow.camera.bottom = -90; scene.add(key);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(100, 100, 20, 20), new THREE.MeshStandardMaterial({ color: 0x171c1b, roughness: .93, metalness: .04 }));
    floor.rotation.x = -Math.PI / 2; floor.position.set(50, 0, 50); floor.receiveShadow = true; scene.add(floor);
    const grid = new THREE.GridHelper(100, 20, 0x34403c, 0x232b29); grid.position.set(50, .03, 50); scene.add(grid);

    const rng = mulberry32(scenario.episode_seed);
    scenario.layout.shelves.forEach((shelf, index) => {
      const [width, depth, height] = shelf.size;
      const unit = new THREE.Group(); unit.position.set(shelf.position[0], 0, shelf.position[1]);
      const frameMaterial = new THREE.MeshStandardMaterial({ color: index % 2 ? 0x4a5653 : 0x414c49, roughness: .58, metalness: .35 });
      for (const x of [-width / 2, width / 2]) for (const z of [-depth / 2, depth / 2]) {
        const post = new THREE.Mesh(new THREE.BoxGeometry(.45, height, .45), frameMaterial); post.position.set(x, height / 2, z); post.castShadow = true; unit.add(post);
      }
      for (const y of [1.2, height * .48, height - .5]) {
        const deck = new THREE.Mesh(new THREE.BoxGeometry(width, .3, depth), frameMaterial); deck.position.y = y; deck.castShadow = true; unit.add(deck);
        for (let item = 0; item < 3; item++) {
          const crate = box([width * .55, 1 + rng() * 1.3, depth * .18], item % 2 ? 0x66533e : 0x59604e);
          crate.position.set((rng() - .5) * width * .25, y + .7, (item - 1) * depth * .27); unit.add(crate);
        }
      }
      scene.add(unit);
    });

    const obstruction = box(scenario.task.obstruction.size, 0xa75e3d, .8); obstruction.position.set(scenario.task.obstruction.position[0], scenario.task.obstruction.size[2] / 2, scenario.task.obstruction.position[1]); obstruction.rotation.y = -scenario.task.obstruction.rotation_deg * Math.PI / 180; scene.add(obstruction);
    const zone = new THREE.Mesh(new THREE.CylinderGeometry(8, 8, .15, 40), new THREE.MeshStandardMaterial({ color: 0x51d7a3, emissive: 0x164d3b, emissiveIntensity: 1.2, transparent: true, opacity: .68 })); zone.position.set(scenario.task.delivery_zone[0], .1, scenario.task.delivery_zone[1]); scene.add(zone);
    const robot = createRobot(); scene.add(robot);
    const parcel = box([.7, .7, .7], 0xffb557, .68); scene.add(parcel);
    const contact = new THREE.Mesh(new THREE.RingGeometry(5, 8, 36), new THREE.MeshBasicMaterial({ color: 0xff5c4f, transparent: true, opacity: 0, side: THREE.DoubleSide })); contact.rotation.x = -Math.PI / 2; scene.add(contact);
    const trailGeometry = new THREE.BufferGeometry();
    const trail = new THREE.Line(trailGeometry, new THREE.LineBasicMaterial({ color: 0xd9ff62, transparent: true, opacity: .55 })); scene.add(trail);

    const resize = () => { const { clientWidth, clientHeight } = mount; renderer.setSize(clientWidth, clientHeight, false); camera.aspect = clientWidth / Math.max(clientHeight, 1); camera.updateProjectionMatrix(); };
    const observer = new ResizeObserver(resize); observer.observe(mount); resize();
    const clock = new THREE.Clock(); let animation = 0; let previousSequence = -1;
    const animate = () => {
      animation = requestAnimationFrame(animate); const current = frameRef.current;
      if (current) {
        robot.position.set(current.robot_x, 0, current.robot_y); robot.rotation.y = -current.heading;
        if (current.shoulder_angle_rad !== null) (robot.userData.shoulder as THREE.Group).rotation.z = -current.shoulder_angle_rad;
        if (current.elbow_angle_rad !== null) (robot.userData.elbow as THREE.Group).rotation.z = -current.elbow_angle_rad;
        parcel.position.set(current.package_x, current.carrying ? 1.25 : .35, current.package_y);
        contact.position.set(current.robot_x, .12, current.robot_y); contact.material.opacity = current.contact_force > 0 ? .75 + Math.sin(clock.elapsedTime * 9) * .2 : 0;
        if (current.sequence !== previousSequence) { (robot.userData.wheels as THREE.Mesh[]).forEach(wheel => wheel.rotation.x += .55); previousSequence = current.sequence; }
        const points = trailRef.current.map(item => new THREE.Vector3(item.robot_x, .18, item.robot_y)); trailGeometry.setFromPoints(points);
      }
      controls.update(); renderer.render(scene, camera);
    }; animate();
    return () => { cancelAnimationFrame(animation); observer.disconnect(); controls.dispose(); renderer.dispose(); trailGeometry.dispose(); scene.traverse(object => { if (object instanceof THREE.Mesh) { object.geometry.dispose(); const materials = Array.isArray(object.material) ? object.material : [object.material]; materials.forEach(material => material.dispose()); } }); mount.removeChild(renderer.domElement); };
  }, [scenario]);

  return <div className="world-shell world-3d"><div className="three-mount" ref={mountRef} />{!frame && <div className="world-empty">Start a run to stream the 3D world state.</div>}<div className="camera-hint">Drag to orbit · Scroll to zoom</div><div className="legend"><span><i className="robot-dot" /> Robot</span><span><i className="package-dot" /> Package</span><span><i className="zone-dot" /> Goal</span></div></div>;
}
