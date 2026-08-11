from __future__ import annotations

import math
import time
from pathlib import Path

import mujoco
import numpy as np

from .contracts import Frame, Run
from .engines import EngineCapabilities
from .evaluator import evaluate
from .evidence import write_evidence_bundle
from .scenario import load_scenario
from .simulator import interpolate
from .store import RunStore


MUJOCO_CAPABILITIES = EngineCapabilities(
    engine_id="mujoco_v1",
    physics=True,
    rigid_body_contacts=True,
    camera_rendering=False,
    deterministic_replay=True,
)


def model_xml(scenario: dict) -> str:
    floor_friction = scenario["world"]["floor_friction"]
    gravity = scenario["world"]["gravity_m_s2"]
    spawn = scenario["agent"]["spawn"]
    package = scenario["task"]["package_spawn"]
    obstruction = scenario["task"]["obstruction"]
    shelves = []
    for index, shelf in enumerate(scenario["layout"]["shelves"]):
        width, depth, height = shelf["size"]
        x, y = shelf["position"]
        shelves.append(
            f'<body name="shelf_{index}" pos="{x} {y} {height / 2}">'
            f'<geom name="shelf_geom_{index}" type="box" size="{width / 2} {depth / 2} {height / 2}" rgba=".25 .3 .28 1" friction="{floor_friction} .02 .001"/>'
            '</body>'
        )
    size = obstruction["size"]
    half = [value / 2 for value in size]
    angle = math.radians(obstruction["rotation_deg"])
    quat = f"{math.cos(angle / 2)} 0 0 {math.sin(angle / 2)}"
    return f"""
<mujoco model="worldsim_warehouse_v0">
  <compiler angle="radian"/>
  <option timestep="0.02" gravity="0 0 -{gravity}" integrator="implicitfast" iterations="80"/>
  <default><geom solref="0.01 1" solimp="0.95 0.99 0.001" condim="4"/></default>
  <worldbody>
    <geom name="floor" type="plane" size="50 50 .1" pos="50 50 0" rgba=".1 .12 .11 1" friction="{floor_friction} .02 .001"/>
    {''.join(shelves)}
    <body name="obstruction" pos="{obstruction['position'][0]} {obstruction['position'][1]} {half[2] + .02}" quat="{quat}">
      <freejoint name="obstruction_joint"/>
      <geom name="obstruction_geom" type="box" size="{half[0]} {half[1]} {half[2]}" mass="35" rgba=".65 .32 .18 1" friction=".8 .03 .002"/>
    </body>
    <body name="package" pos="{package[0]} {package[1]} .37">
      <freejoint name="package_joint"/>
      <geom name="package_geom" type="box" size=".35 .35 .35" mass="8" rgba="1 .55 .2 1" friction=".65 .02 .001"/>
    </body>
    <body name="robot" pos="{spawn[0]} {spawn[1]} .46">
      <joint name="robot_x" type="slide" axis="1 0 0" damping="90"/>
      <joint name="robot_y" type="slide" axis="0 1 0" damping="90"/>
      <joint name="robot_yaw" type="hinge" axis="0 0 1" damping="35"/>
      <geom name="robot_geom" type="cylinder" size=".72 .42" mass="118" rgba=".7 .9 .2 1" friction=".9 .03 .002"/>
      <body name="shoulder_link" pos="0 0 1.15" gravcomp="1">
        <joint name="shoulder_joint" type="hinge" axis="0 1 0" range="-1.3 1.3" damping="12"/>
        <geom name="robot_upper_arm" type="capsule" fromto="0 0 0 .8 0 0" size=".1" mass="9" rgba=".55 .67 .2 1"/>
        <body name="elbow_link" pos=".8 0 0">
          <joint name="elbow_joint" type="hinge" axis="0 1 0" range="-1.8 1.8" damping="9"/>
          <geom name="robot_forearm" type="capsule" fromto="0 0 0 .7 0 0" size=".08" mass="6" rgba=".63 .76 .24 1"/>
          <body name="gripper" pos=".7 0 0">
            <geom name="robot_palm" type="box" size=".1 .2 .14" mass="2" rgba=".12 .15 .14 1"/>
            <body name="left_finger" pos=".12 .1 0">
              <joint name="left_gripper_joint" type="slide" axis="0 1 0" range="0 .15" damping="4"/>
              <geom name="robot_left_finger" type="box" size=".2 .03 .05" mass=".4" rgba=".7 .9 .2 1"/>
            </body>
            <body name="right_finger" pos=".12 -.1 0">
              <joint name="right_gripper_joint" type="slide" axis="0 -1 0" range="0 .15" damping="4"/>
              <geom name="robot_right_finger" type="box" size=".2 .03 .05" mass=".4" rgba=".7 .9 .2 1"/>
            </body>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
  <actuator>
    <position name="drive_x" joint="robot_x" kp="600" kv="150"/>
    <position name="drive_y" joint="robot_y" kp="600" kv="150"/>
    <position name="drive_yaw" joint="robot_yaw" kp="180" kv="45"/>
    <position name="shoulder_motor" joint="shoulder_joint" kp="1200" kv="120"/>
    <position name="elbow_motor" joint="elbow_joint" kp="800" kv="90"/>
    <position name="left_gripper_motor" joint="left_gripper_joint" kp="80" kv="12"/>
    <position name="right_gripper_motor" joint="right_gripper_joint" kp="80" kv="12"/>
  </actuator>
</mujoco>
""".strip()


class MujocoEngine:
    capabilities = MUJOCO_CAPABILITIES

    def __init__(self, scenario_path: Path):
        self.scenario_path = scenario_path

    def execute(self, store: RunStore, run: Run, evidence_root: Path, frame_delay: float) -> dict:
        scenario = load_scenario(self.scenario_path, run.seed)
        xml = model_xml(scenario)
        model = mujoco.MjModel.from_xml_string(xml)
        data = mujoco.MjData(model)
        store.update_run(run.id, status="loading", progress=.04, phase="Compiling MuJoCo model")
        store.add_event(run.id, 1, "engine", f"MuJoCo {mujoco.__version__} model compiled", 0)

        # Settle dynamic task objects on the floor before episode time begins.
        for _ in range(100):
            mujoco.mj_step(model, data)
        data.time = 0
        package_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "package_joint")
        package_qpos = model.jnt_qposadr[package_joint]
        package_dof = model.jnt_dofadr[package_joint]
        package_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "package")
        robot_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "robot")
        robot_geom_ids = {index for index in range(model.ngeom)
                          if (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, index) or "").startswith("robot_")}
        joint_ids = {name: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) for name in
                     ("robot_x", "robot_y", "robot_yaw", "shoulder_joint", "elbow_joint",
                      "left_gripper_joint", "right_gripper_joint")}
        qpos_addresses = {name: model.jnt_qposadr[joint_id] for name, joint_id in joint_ids.items()}
        dof_addresses = {name: model.jnt_dofadr[joint_id] for name, joint_id in joint_ids.items()}
        obstruction = scenario["task"]["obstruction"]["position"]
        package_spawn = scenario["task"]["package_spawn"]
        spawn = tuple(scenario["agent"]["spawn"])
        goal = tuple(scenario["task"]["delivery_zone"])
        if run.policy_id == "baseline_risky":
            waypoints = [spawn, (10, 52), (32, 52), tuple(obstruction), tuple(package_spawn), goal]
        else:
            # Clearance-aware route: descend the west corridor, traverse the central aisle,
            # pass north of the obstruction, then approach the package from open space.
            waypoints = [spawn, (10, 52), (32, 52), (36, 60),
                         (58, 60), (68, 40), tuple(package_spawn), goal]
        trajectory = list(interpolate(waypoints, steps_per_leg=36))
        trajectory.extend([(len(waypoints) - 2, goal[0], goal[1])] * 30)
        carrying_leg = len(waypoints) - 2
        frames: list[dict] = []
        collisions = 0
        max_force = 0.0
        measured_samples = 0
        collision_geometries: dict[str, int] = {}
        event_sequence = 2
        contact_active = False
        cumulative_energy = 0.0
        grasp_recorded = False
        store.update_run(run.id, status="running", progress=.08, phase="Executing rigid-body episode")

        for sequence, (leg, x, y) in enumerate(trajectory):
            next_index = min(sequence + 1, len(trajectory) - 1)
            _, nx, ny = trajectory[next_index]
            heading = math.atan2(ny - y, nx - x)
            carrying = leg >= carrying_leg
            frame_force = 0.0
            frame_contact_name = "unknown"
            for substep in range(5):
                fraction = (substep + 1) / 5
                target_x = x + (nx - x) * fraction
                target_y = y + (ny - y) * fraction
                shoulder_target = -1.02
                elbow_target = 1.30
                finger_target = .01 if carrying else .12
                data.ctrl[:] = [target_x - spawn[0], target_y - spawn[1], heading,
                                shoulder_target, elbow_target, finger_target, finger_target]
                if carrying:
                    robot_position = data.xpos[robot_body]
                    data.qpos[package_qpos:package_qpos + 7] = [robot_position[0] + math.cos(heading) * 1.2,
                                                                robot_position[1] + math.sin(heading) * 1.2, 1.25, 1, 0, 0, 0]
                    data.qvel[package_dof:package_dof + 6] = 0
                mujoco.mj_step(model, data)
                cumulative_energy += float(np.sum(np.abs(data.qfrc_actuator * data.qvel))) * model.opt.timestep
                for contact_index in range(data.ncon):
                    contact = data.contact[contact_index]
                    robot_contact_geom = contact.geom1 if contact.geom1 in robot_geom_ids else contact.geom2 if contact.geom2 in robot_geom_ids else None
                    if robot_contact_geom is None:
                        continue
                    other = contact.geom2 if contact.geom1 == robot_contact_geom else contact.geom1
                    other_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, other) or ""
                    if not (other_name == "obstruction_geom" or other_name.startswith("shelf_geom_")):
                        continue
                    force = np.zeros(6)
                    mujoco.mj_contactForce(model, data, contact_index, force)
                    magnitude = float(np.linalg.norm(force[:3]))
                    if magnitude > frame_force:
                        frame_force = magnitude
                        frame_contact_name = other_name
                    measured_samples += 1
            colliding = frame_force > 1.0
            if colliding and not contact_active:
                collisions += 1
                collision_geometries[frame_contact_name] = collision_geometries.get(frame_contact_name, 0) + 1
                store.add_event(run.id, event_sequence, "contact", f"Measured contact with {frame_contact_name}: {frame_force:.1f} N", sequence * .1)
                event_sequence += 1
            contact_active = colliding
            max_force = max(max_force, frame_force)
            if carrying and not grasp_recorded:
                store.add_event(run.id, event_sequence, "task", "Package grasp state engaged", sequence * .1)
                event_sequence += 1
                grasp_recorded = True
            package_position = data.xpos[package_body]
            robot_position = data.xpos[robot_body]
            shoulder_angle = float(data.qpos[qpos_addresses["shoulder_joint"]])
            elbow_angle = float(data.qpos[qpos_addresses["elbow_joint"]])
            left_finger = float(data.qpos[qpos_addresses["left_gripper_joint"]])
            right_finger = float(data.qpos[qpos_addresses["right_gripper_joint"]])
            frame = Frame(sequence=sequence, sim_time=round(sequence * .1, 2), robot_x=float(robot_position[0]),
                          robot_y=float(robot_position[1]), heading=float(data.qpos[qpos_addresses["robot_yaw"]]),
                          package_x=float(package_position[0]), package_y=float(package_position[1]),
                          carrying=carrying, contact_force=round(frame_force, 3),
                          linear_speed_m_s=round(math.hypot(float(data.qvel[dof_addresses["robot_x"]]), float(data.qvel[dof_addresses["robot_y"]])), 4),
                          angular_speed_rad_s=round(float(data.qvel[dof_addresses["robot_yaw"]]), 4),
                          shoulder_angle_rad=round(shoulder_angle, 4), elbow_angle_rad=round(elbow_angle, 4),
                          gripper_width_m=round(.20 + left_finger + right_finger, 4), energy_j=round(cumulative_energy, 3))
            store.add_frame(run.id, frame)
            frames.append(frame.model_dump())
            store.update_run(run.id, status="running", progress=.08 + .84 * ((sequence + 1) / len(trajectory)),
                             phase="Delivering package" if carrying else "Navigating with MuJoCo physics")
            time.sleep(frame_delay)

        final_package = frames[-1]
        delivery_distance = math.dist((final_package["package_x"], final_package["package_y"]), goal)
        metrics = {"task_completed": delivery_distance <= 10, "delivery_error_m": round(delivery_distance, 3), "collisions": collisions,
                   "collision_geometries": collision_geometries,
                   "max_contact_force_n": round(max_force, 3), "sim_duration_s": frames[-1]["sim_time"],
                   "frames_recorded": len(frames), "physics_steps": len(frames) * 5,
                   "measured_contact_samples": measured_samples, "deterministic_seed": run.seed}
        verdict, checks = evaluate(metrics, scenario)
        metrics["checks"] = checks
        store.update_run(run.id, status="finalizing", progress=.96, phase="Writing physics evidence")
        run_dir = evidence_root / "runs" / run.id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "model.xml").write_text(xml, encoding="utf-8")
        evidence = {"schema_version": "2.0", "frame_schema_version": "2.0", "engine": {**self.capabilities.__dict__, "version": mujoco.__version__},
                    "run_id": run.id, "scenario_id": run.scenario_id, "policy_id": run.policy_id,
                    "seed": run.seed, "verdict": verdict, "metrics": metrics,
                    "scenario_snapshot": scenario, "trajectory": frames}
        write_evidence_bundle(run_dir, evidence)
        store.add_event(run.id, event_sequence, "verdict", f"Physics run {verdict.upper()}", frames[-1]["sim_time"])
        store.update_run(run.id, status="succeeded" if verdict == "pass" else "failed", progress=1,
                         phase="Physics evaluation complete", verdict=verdict, metrics=metrics)
        return evidence
