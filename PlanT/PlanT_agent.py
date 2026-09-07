import os
import re
import json
import yaml
from pathlib import Path
from datetime import datetime
from collections import deque

import cv2
import torch
import numpy as np
import torch.nn.functional as F
from scipy.interpolate import PchipInterpolator

import carla
from srunner.scenariomanager.timer import GameTime

from data_agent import DataAgent
from dataset import generate_batch 
from lit_module import LitHFLM
import transfuser_utils as t_u
from lateral_controller import LateralPIDController
from util.viz_batch import viz_batch
from birds_eye_view.chauffeurnet import ObsManager
from longitudinal_controller import LongitudinalLinearRegressionController
from plant_variables import PlanTVariables
from util.static_extents import STATIC_EXTENTS, CAR_EXTENTS
from relation_features import relationize_exact_row, filter_planner_tokens

def get_entry_point():
    return 'PlanTAgent'


def rad2deg(theta):
    return t_u.normalize_angle_degree(np.rad2deg(theta))

class PlanTAgent(DataAgent):
    def setup(self, path_to_conf_file, route_index=None, traffic_manager=None):

        self.control_history = [(0,0,0) for _ in range(25)]

        self.img_path = os.environ["PLANT_VIZ"]
        self.visualize_plant = len(self.img_path) > 0
        if self.visualize_plant:
            self.img_path = os.path.join(self.img_path, datetime.now().strftime("%H:%M:%S_%d-%m-%Y"))
            os.makedirs(self.img_path, exist_ok=True)
        
        self.use_rgb = True # eval_config["viz_img"]
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.route_index = route_index
        print("Route index:", self.route_index)

        super().setup(path_to_conf_file, route_index, traffic_manager)

        LOAD_CKPT_PATH = os.environ["PLANT_CHECKPOINT"]

        self.cfg_net = torch.load(LOAD_CKPT_PATH, map_location="cpu", weights_only=False)["hyper_parameters"]["cfg"]
        self.input_bev = self.cfg_net["model"]["training"].get("input_bev", False)
        self.input_static_cars = self.cfg_net["model"]["training"].get("input_static_cars", False)

        self.input_range = self.cfg_net["model"]["training"].get("range", False)
        self.input_range_factor_front = self.cfg_net["model"]["training"].get("range_factor_front", False)

        self.input_representation = self.cfg_net["model"]["training"].get(
            "input_representation", "exact"
        )

        self.input_remove_stop_sign_token = self.cfg_net["model"]["training"].get(
            "remove_stop_sign_token", False
        )

        print("Input representation:", self.input_representation)
        print(f"BEV: {self.input_bev}, Static: {self.input_static_cars}")
        print(f"Range: {self.input_range}, front factor: {self.input_range_factor_front}")
        print(f'Loading model from {LOAD_CKPT_PATH}')

        # Gate 4.5A: zero-training diagnostic JSONL log
        tm_seed = os.environ.get("GATE45A_TM_SEED", "100")
        route_tag = str(self.route_index).replace("/", "_").replace(".xml", "") if self.route_index else "noroute"
        self._gate45a_log_path = os.path.join(
            os.path.abspath(os.getcwd()), "outputs", "gate45a",
            f"{self.input_representation}_route{route_tag}_tm{tm_seed}.jsonl",
        )
        os.makedirs(os.path.dirname(self._gate45a_log_path), exist_ok=True)
        print("Gate4.5A debug log:", self._gate45a_log_path)

        # Gate 6: logging / snapshot switches (debug only; never change forward)
        self._gate6_on = bool(
            os.environ.get("GATE6_SMOKE", "0") == "1"
            or os.environ.get("GATE6_SNAP", "0") == "1"
        )
        self._gate6_tag = route_tag
        self._dbg_actor_ids = None

        if Path(LOAD_CKPT_PATH).suffix == '.ckpt':
            self.net = LitHFLM.load_from_checkpoint(LOAD_CKPT_PATH, map_location=self.device)
        else:
            raise Exception(f'Unknown model type: {Path(LOAD_CKPT_PATH).suffix}')
        self.net.eval()

        self.cleared_stop_sign = False
        self.moving_walkers = set()

        self.lat_pid = LateralPIDController(self.config)
        self.lon_pid = LongitudinalLinearRegressionController(self.config)

        self.plant_vars = PlanTVariables()
        self.speed_cats = self.plant_vars.speed_cats
        self.bev_colors = torch.tensor(self.plant_vars.bev_colors)

    def _init(self, hd_map):
        super()._init(hd_map)

        self.control = carla.VehicleControl()
        self.control.steer = 0.0
        self.control.throttle = 0.0
        self.control.brake = 1.0

        # Gate 4.5C: stop-sign token deadlock detector state (debug only)
        self._debug_force_clear = False
        self._deadlock_low_speed_frames = 0
        self._deadlock_dist_hist = deque(maxlen=40)

        if self.input_bev:
            obs_config = {
                'width_in_pixels': self.config.lidar_resolution_width,
                'pixels_ev_to_bottom': self.config.lidar_resolution_height / 2.0,
                'pixels_per_meter': self.config.pixels_per_meter_collection,
                'history_idx': [-1],
                'scale_bbox': True,
                'scale_mask_col': 1.0,
                'map_folder': 'maps_2ppm_cv'
            }

            self.ss_bev_manager = ObsManager(obs_config, self.config)
            self.ss_bev_manager.attach_ego_vehicle(self._vehicle, criteria_stop=self.stop_sign_criteria)

        self.initialized = True

    def sensors(self):
        result = [{
            "type": "sensor.other.imu",
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "sensor_tick": 0.05,
            "id": "imu"
        }, {
            "type": "sensor.speedometer",
            "reading_frequency": 20,
            "id": "speed"
        },{
            'type': 'sensor.other.gnss',
            'x': 0.0, 'y': 0.0, 'z': 0.0,
            'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0,
            'sensor_tick': 0.01,
            'id': 'gps'
            }]
        
        if self.visualize_plant and self.use_rgb:
            result.append({
            'type': 'sensor.camera.rgb',
            'x': self.config.camera_pos[0],
            'y': self.config.camera_pos[1],
            'z': self.config.camera_pos[2],
            'roll': self.config.camera_rot_0[0],
            'pitch': self.config.camera_rot_0[1],
            'yaw': self.config.camera_rot_0[2],
            'width': 1024, # self.config.camera_width,
            'height': 512, # self.config.camera_height,
            'fov': self.config.camera_fov,
            'id': 'rgb'
            })

        return result

    def tick(self, input_data):
        result = {}

        loc = self._vehicle.get_location()
        pos = np.array([loc.x, loc.y, loc.z])
        speed = input_data['speed'][1]['speed']
        compass = t_u.preprocess_compass(input_data['imu'][1][-1])

        if self.visualize_plant and self.use_rgb:
            result["rgb"] = input_data["rgb"]
        result["speed"] = speed
        result["yaw"] = t_u.normalize_angle(compass)

        result['gps'] = pos[:2]

        if self.input_bev:
            bev = self.ss_bev_manager.get_observation(None)['bev_semantic_classes']
            bev = np.rot90(bev)
            bev = self.bev_colors[torch.tensor(bev[64:-64, 64:-64].copy(), dtype=torch.int)].permute(2, 0, 1)
            result["BEV"] = bev

        return result

    @torch.no_grad()
    def run_step(self, input_data, timestamp, sensors=None):
        self.step += 1
        if not self.initialized:
            self._init(None)

        tick_data = self.tick(input_data)

        # Route wps
        self._waypoint_planner.load()
        _, _, _, next_light_dist, next_traffic_light, next_stop_dist, next_stop_sign, speed_limit = self._waypoint_planner.run_step(tick_data["gps"])

        # Gate 4.5A: stash real route rule-object state for the debug log
        if next_traffic_light is not None:
            self._dbg_next_light_state = str(next_traffic_light.state)
            self._dbg_next_light_id = int(next_traffic_light.id)
        else:
            self._dbg_next_light_state = None
            self._dbg_next_light_id = None
        self._dbg_next_light_dist = float(next_light_dist) if next_light_dist is not None else None
        self._dbg_next_stop_dist = float(next_stop_dist) if next_stop_dist is not None else None
        self._dbg_has_next_stop_sign = next_stop_sign is not None

        waypoint_route = self._waypoint_planner.original_route_points[self._waypoint_planner.route_index:][self.config.tf_first_checkpoint_distance:][::self.config.points_per_meter]
        self.waypoint_route = waypoint_route[:20, :2]
        self._waypoint_planner.save()

        tick_data["speed_limit"] = self.speed_cats[round(speed_limit*3.6)]

        tick_data["route"] = np.array([t_u.inverse_conversion_2d(p, tick_data['gps'], tick_data["yaw"]) for i, p in enumerate(self.waypoint_route)])

        # Boxes
        label_raw = self.get_bounding_boxes()

        for x in label_raw:
            if "position" in x:
                pos_x, pos_y, pos_z = x["position"]
                x_div = self.input_range_factor_front**2 if pos_x > 0 else 1
                if pos_x**2/x_div + pos_y**2 > self.input_range**2 or abs(pos_z) > 30:
                    x["class"] = "too far"

        ego_vehicle_location = self._vehicle.get_location()
        ego_transform = self._vehicle.get_transform()

        # Debug label above ego: identify which model is driving this window
        label = "EXACT" if self.input_representation == "exact" else "RELATION"
        label_color = carla.Color(0, 255, 0) if label == "EXACT" else carla.Color(255, 0, 0)
        self._world.debug.draw_string(
            ego_transform.location + carla.Location(z=3.0),
            label, color=label_color, draw_shadow=True, life_time=0.1,
        )

        ego_matrix = np.array(ego_transform.get_matrix())
        ego_rotation = ego_transform.rotation
        ego_yaw = np.deg2rad(ego_rotation.yaw)
        ego_vehicle_speed = self._vehicle.get_velocity().length()

        # Traffic lights
        if next_traffic_light is not None and next_light_dist < 30:
            for light, _, waypoints in self.list_traffic_lights:
                if light.id != next_traffic_light.id:
                    continue

                global_rot = light.get_transform().rotation
                relative_yaw = t_u.normalize_angle(np.deg2rad(global_rot.yaw) - ego_yaw)
                for wp in waypoints:
                    relative_pos = t_u.get_relative_transform(ego_matrix, np.array(wp.transform.get_matrix()))
                    label_raw.append({
                        'class': 'traffic_light',
                        'extent': [1.5, 1.5, 0.5],
                        'position': [relative_pos[0], relative_pos[1], relative_pos[2]],
                        'yaw': relative_yaw,
                        'state': str(light.state)
                        })

        # Stop sign
        if next_stop_sign is not None and not self.cleared_stop_sign and next_stop_dist < 30:
            center_bb_stop_sign = next_stop_sign.get_transform().transform(next_stop_sign.trigger_volume.location)
            stop_wp = self.world_map.get_waypoint(center_bb_stop_sign)
            rotation_stop_sign = next_stop_sign.get_transform().rotation
            relative_yaw = t_u.normalize_angle(np.deg2rad(rotation_stop_sign.yaw) - ego_yaw)
            relative_pos = t_u.get_relative_transform(ego_matrix, np.array(stop_wp.transform.get_matrix()))

            label_raw.append({
                        'class': 'stop_sign',
                        'extent': [1.5, 1.5, 0.5],
                        'position': [relative_pos[0], relative_pos[1], relative_pos[2]],
                        'yaw': relative_yaw
                        })

        # Calculate the accurate distance to the stop sign
        if next_stop_sign is not None:
            distance_to_stop_sign = next_stop_sign.get_transform().transform(next_stop_sign.trigger_volume.location) \
                .distance(ego_vehicle_location)
        else:
            distance_to_stop_sign = 999999999

        # Reset the stop sign flag if we are farther than 10m away
        if distance_to_stop_sign > self.config.unclearing_distance_to_stop_sign:
            self.cleared_stop_sign = False
        else:
            # Set the stop sign flag if we are closer than 3m and speed is low enough
            if ego_vehicle_speed < 0.1 and distance_to_stop_sign < self.config.clearing_distance_to_stop_sign:
                self.cleared_stop_sign = True

        # Gate 4.5C: stop-sign token deadlock detector (debug only; never changes driving unless env-gated drop in get_input_batch)
        ego_spd_deadlock = float(tick_data["speed"])
        stop_token_present = (
            next_stop_sign is not None
            and not self.cleared_stop_sign
            and next_stop_dist is not None
            and next_stop_dist < 30
        )
        if ego_spd_deadlock < 0.1:
            self._deadlock_low_speed_frames += 1
        else:
            self._deadlock_low_speed_frames = 0
        self._deadlock_dist_hist.append(float(distance_to_stop_sign))
        dist_2s = self._deadlock_dist_hist[0] if len(self._deadlock_dist_hist) >= 40 else None
        deadlock_detected = bool(
            stop_token_present
            and self._deadlock_low_speed_frames >= 40
            and distance_to_stop_sign >= 3.0
            and (dist_2s is not None and abs(distance_to_stop_sign - dist_2s) < 0.2)
        )
        if deadlock_detected:
            self._debug_force_clear = True
        if next_stop_sign is None or next_stop_dist is None or next_stop_dist > 30.0:
            self._debug_force_clear = False
            self._deadlock_low_speed_frames = 0
        self._dbg_deadlock = {
            "deadlock_detected": deadlock_detected,
            "debug_force_clear": self._debug_force_clear,
            "distance_to_stop_sign": float(distance_to_stop_sign),
            "distance_2s_ago": dist_2s,
            "low_speed_frames": self._deadlock_low_speed_frames,
            "stop_token_present": stop_token_present,
        }

        # Gate 6 smoke: minimal scenario annotation (debug only, env-gated)
        self._dbg_scenario = None
        if os.environ.get("GATE6_SMOKE", "0") == "1":
            try:
                sc_actors = []
                for _x in label_raw:
                    if _x.get("scenario") and _x["class"].lower() in self.plant_vars.car_types:
                        sc_actors.append({
                            "id": int(_x["id"]) if "id" in _x else None,
                            "class": _x["class"],
                            "scenario": _x["scenario"],
                            "x_ego": float(_x["position"][0]),
                            "y_ego": float(_x["position"][1]),
                            "yaw_rel_deg": float(rad2deg(_x["yaw"])),
                            "speed_kmh": float(_x["speed"]) * 3.6,
                            "width_m": float(_x["extent"][1] * 2),
                            "length_m": float(_x["extent"][0] * 2),
                        })
                self._dbg_scenario = {
                    "active_scenarios": sorted({a["scenario"] for a in sc_actors}),
                    "actors": sc_actors,
                }
            except Exception:
                self._dbg_scenario = None

        self.control = self._get_control(label_raw, tick_data)

        inital_frames_delay = 40
        if self.step < inital_frames_delay:
            self.control = carla.VehicleControl(0.0, 0.0, 1.0)

        return self.control

    # In: Waypoints NxD
    # Out: Waypoints NxD equally spaced 0.1 across D
    def interpolate_waypoints(self, waypoints):
        waypoints = waypoints.copy()
        waypoints = np.concatenate((np.zeros_like(waypoints[:1]), waypoints))
        shift = np.roll(waypoints, 1, axis=0)
        shift[0] = shift[1]

        dists = np.linalg.norm(waypoints-shift, axis=1)
        dists = np.cumsum(dists)
        dists += np.arange(0, len(dists)) * 1e-4 # Prevents dists not being strictly increasing

        interp = PchipInterpolator(dists, waypoints, axis=0)

        x = np.arange(0.1, dists[-1], 0.1)

        interp_points = interp(x)

        # There is a possibility that all points are at 0, meaning there is no point distanced 0.1
        # In this case we output the last (assumed to be furthest) waypoint.
        if interp_points.shape[0] == 0:
            interp_points = waypoints[None, -1]

        return interp_points

    def _get_control(self, label_raw, input_data):
        gt_velocity = input_data['speed'] # torch.FloatTensor([input_data['speed']]).unsqueeze(0)
        input_batch = self.get_input_batch(label_raw, input_data)

        for x in input_batch:
            input_batch[x] = input_batch[x].to(self.device) # Does it work inplace?

        input_batch["y_objs"] = None

        (pred_path, pred_wps, pred_speed) = self.net(input_batch)[2]

        if pred_path is not None:
            pred_path = pred_path.detach().squeeze().cpu().numpy()
        if pred_wps is not None:
            pred_wps = pred_wps.detach().squeeze().cpu().numpy()

        # Gate 6: optional full-forward snapshot capture at ~5 Hz (debug only)
        if self._gate6_on and os.environ.get("GATE6_SNAP", "0") == "1":
            try:
                if self.step > 40 and self.step % 4 == 0:
                    self._gate6_capture(input_batch, pred_path, pred_wps, input_data)
            except Exception:
                pass

        desired_speed_raw = None
        mean_speed_raw = None
        if pred_speed is not None:
            pred_speed = pred_speed.detach().squeeze().cpu()
            pred_speed = F.softmax(pred_speed, dim=0)
            pred_speed = pred_speed.numpy()
            pred_speed = np.array([0.0, 4.0, 8.0, 10, 13.88888888, 16, 17.77777777, 20]) * pred_speed
            desired_speed_raw = float(sum(pred_speed))
            desired_speed = desired_speed_raw
        else:
            desired_speed_raw = float(np.linalg.norm((pred_wps[2] - pred_wps[3])) * 4.0) # Using 3rd and 4th waypoint for speed

            # Creep heuristic
            mean_speed_raw = float(np.linalg.norm(pred_wps[:-1] - pred_wps[1:], axis=-1).mean() * 4.0)
            desired_speed = desired_speed_raw
            if gt_velocity < 0.01:
                desired_speed = min(mean_speed_raw, 0.1)

        throttle, brake = self.lon_pid.get_throttle_and_brake(desired_speed < 0.05, desired_speed, gt_velocity)

        #### Steering 
        if pred_path is None:
            interp_wp = self.interpolate_waypoints(pred_wps)
        else:
            interp_wp = self.interpolate_waypoints(pred_path)

        if gt_velocity < 0.05 and brake:
            # Integral accumulation
            steer = self.lat_pid.step(np.array([[1.0, 0.0], [2.0, 0.0], [3.0, 0.0], [4.0, 0.0]]), gt_velocity, np.array([0., 0.]), 0., False)
        else:
            steer = self.lat_pid.step(interp_wp, gt_velocity, np.array([0., 0.]), 0., False)

        self.control_history.append((float(steer), float(throttle), float(brake)))
        self.control_history = self.control_history[1:]

        control = carla.VehicleControl()
        control.steer = float(steer)
        control.throttle = float(throttle)
        control.brake = float(brake)

        viz_trigger = self.step % 5 == 0 and self.visualize_plant
        if viz_trigger and self.step > 2:
            for x in input_batch:
                if input_batch[x] is None:
                    continue
                input_batch[x] = input_batch[x].cpu()

            if pred_wps is not None:
                input_batch["waypoints"] = [pred_wps]
            else:
                input_batch["waypoints"] = [[]]

            if pred_path is not None:
                input_batch["pred_path"] = [pred_path]
            else:
                input_batch["pred_path"] = [[]]

            record = {"boxes": input_batch["x_objs"][2:].tolist(), # Fine for agent
                    "ego_pos": input_data["gps"].tolist(),
                    "ego_rot": input_data["yaw"],
                    "waypoints": np.array(input_batch["waypoints"][0]).tolist(),
                    "route_original": np.array(input_batch["route_original"][0]).tolist(),
                    "route": np.array(input_batch["pred_path"][0]).tolist(),
                    "control_history": self.control_history,
                    "frame": GameTime.get_frame(),
                    "ego_speed": round(input_data["speed"], 2)}

            with open(f"{self.img_path}.txt", "a") as f:
                line = json.dumps(record) + "\n"
                line = re.sub(r'(\d+\.\d{3})\d*', r'\1', line)
                f.write(line)

            if self.use_rgb and self.step % 20 == 0:
                img = viz_batch(input_batch, rgb=input_data["rgb"], range_front=self.input_range*self.input_range_factor_front, range_sides=self.input_range)#, control_history=self.control_history) #, input_ego=self.cfg_agent.model.training.input_ego)
                cv2.imwrite(f"{self.img_path}/{GameTime.get_frame()}.jpg", img)

        # Gate 4.5A: zero-training diagnostic JSONL log (must never break driving)
        try:
            dbg = getattr(self, "_dbg_relation", None) or {}
            record = {
                "frame": int(GameTime.get_frame()),
                "ego_speed": float(gt_velocity),
                "desired_speed_raw": desired_speed_raw,
                "mean_speed_raw": mean_speed_raw,
                "desired_speed_after_creep": float(desired_speed),
                "hazard_brake": bool(desired_speed < 0.05),
                "throttle": float(throttle),
                "brake": bool(brake),
                "steer": float(steer),
                "next_light_id": getattr(self, "_dbg_next_light_id", None),
                "next_light_state": getattr(self, "_dbg_next_light_state", None),
                "next_light_dist": getattr(self, "_dbg_next_light_dist", None),
                "next_stop_dist": getattr(self, "_dbg_next_stop_dist", None),
                "has_next_stop_sign": bool(getattr(self, "_dbg_has_next_stop_sign", False)),
                "ego_pos": [float(x) for x in input_data["gps"]],
                "ego_yaw": float(input_data["yaw"]),
                "num_type5_tokens": int(dbg.get("num_type5_tokens", 0)),
                "num_type4_tokens": int(dbg.get("num_type4_tokens", 0)),
                "num_dangerous": int(dbg.get("num_dangerous", 0)),
                "num_masked": int(dbg.get("num_masked", 0)),
                "num_objects_before_mask": int(dbg.get("num_objects_before_mask", 0)),
                "num_objects_after_mask": int(dbg.get("num_objects_after_mask", 0)),
                "deadlock_detected": bool(dbg.get("deadlock_detected", False)),
                "force_clear_active": bool(dbg.get("force_clear_active", False)),
                "num_type4_tokens_before": int(dbg.get("num_type4_tokens_before", 0)),
                "num_type4_tokens_after": int(dbg.get("num_type4_tokens_after", 0)),
                "distance_to_stop_sign": dbg.get("distance_to_stop_sign", None),
                "low_speed_frames": int(dbg.get("low_speed_frames", 0)),
                "has_lead_vehicle": bool(dbg.get("has_lead_vehicle", False)),
                "dangerous_relations": dbg.get("dangerous_relations", []),
                "pred_wps": pred_wps.tolist() if pred_wps is not None else None,
                "pred_path": pred_path.tolist() if pred_path is not None else None,
            }
            _scn = getattr(self, "_dbg_scenario", None)
            if _scn is not None:
                record["active_scenarios"] = _scn["active_scenarios"]
                record["scenario_actors"] = _scn["actors"]
            with open(self._gate45a_log_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

        return control
    
    
    def get_input_batch(self, label_raw, input_data):
        sample = {'input': [], 'output': [], 'route': [], 'waypoints': [], 'target_point': []}

        car_types = self.plant_vars.car_types
        type_nums = self.plant_vars.class_nums

        # Statics don't appear in longest6
        if self.route_index and "longest6" in self.route_index:
            type_nums.pop("static", None)

        if not self.input_static_cars:
            type_nums.pop("static_car", None)
        
        for x in label_raw:
            # We skip walkers that haven't moved yet, but keep walkers that have already moved
            # (Walkers may run into a vehicle, stop, be removed from input because they dont move, plant causes crash)
            if x["class"] == "walker":
                if x["speed"] < 0.1 and x["id"] not in self.moving_walkers:
                    x["class"] = "irrelevant_walker"
                else:
                    self.moving_walkers.add(x["id"])
            
            elif x["class"] == "car" and x["type_id"] in ["vehicle.dodge.charger_police",
                                                        "vehicle.dodge.charger_police_2020",
                                                        "vehicle.carlamotors.firetruck",
                                                        "vehicle.ford.ambulance"]:
                x["class"] = "emergency"

            elif x["class"] == "static":
                if "type_id" in x.keys() and x["type_id"] not in ["static.prop.constructioncone", 
                                                                    "static.prop.trafficwarning"]:
                    x["class"] = "irrelevant_static"
                else:
                    # # update static extent
                    if x["type_id"] in STATIC_EXTENTS:
                        x["extent"] = STATIC_EXTENTS[x["type_id"]]
                    else:
                        print(x["type_id"], "was not found in static extents")

            elif x["class"] == "static_car":
                if x["mesh_path"] in CAR_EXTENTS:
                    x["extent"] = CAR_EXTENTS[x["mesh_path"]]
                    if "scale" in x.keys() and x["scale"] is not None:
                        scale = float(x["scale"])
                        x["extent"] = [a*scale for a in x["extent"]]
                else:
                    print("missing static car:", x["mesh_path"])

        data_car = [
            [
                type_nums[x["class"].lower()],  # type indicator
                x['position'][0],
                x['position'][1],
                rad2deg(x['yaw']), # in degrees
                x['speed'] * 3.6, # in km/h
                x['extent'][1]*2 + (0 if "scenario" not in x.keys() or "Door" not in x["scenario"] else 1),
                x['extent'][0]*2
            ]
            for j, x in enumerate(label_raw)
            if x["class"].lower() in car_types
        ]

        data_car += [[
                type_nums[x["class"].lower()], # type indicator
                x['position'][0],
                x['position'][1],
                rad2deg(x['yaw']), # in degrees
                0.0,
                x['extent'][1]*2,
                x['extent'][0]*2
            ]
            for j, x in enumerate(label_raw)
            if x["class"].lower() not in car_types and x["class"].lower() in type_nums.keys() and (not x["class"].lower()=="traffic_light" or x["state"] in ["Red", "Yellow"])
        ] 

        # Gate 4.5A: raw exact copy before relationize, used only for debug
        data_car_exact_raw = [list(row) for row in data_car]

        # Gate 6: actor_id per token row (must align with data_car order)
        self._dbg_actor_ids = None
        if self._gate6_on:
            try:
                ids = []
                for x in label_raw:
                    if x["class"].lower() in car_types:
                        ids.append(x.get("id"))
                for x in label_raw:
                    if (x["class"].lower() not in car_types
                            and x["class"].lower() in type_nums.keys()
                            and (not x["class"].lower() == "traffic_light" or x["state"] in ["Red", "Yellow"])):
                        ids.append(x.get("id"))
                if len(ids) == len(data_car):
                    self._dbg_actor_ids = ids
            except Exception:
                self._dbg_actor_ids = None

        if self.input_representation == "relation":
            if len(label_raw) == 0:
                raise RuntimeError("No CARLA bounding-box data available.")

            ego_obj = label_raw[0]
            if "extent" not in ego_obj:
                raise RuntimeError("Ego bounding box has no extent.")

            data_car = [
                relationize_exact_row(
                    row,
                    ego_speed_mps=input_data["speed"],
                    ego_extent=ego_obj["extent"],
                )
                for row in data_car
            ]

        # Gate 4.6: shared filter removing stop-sign tokens from planner input
        if self.input_remove_stop_sign_token:
            data_car = filter_planner_tokens(data_car, True)

        # Gate 4.5A: token counts + dangerous relations + lead vehicle (debug only)
        num_type5_tokens = sum(1 for r in data_car if int(round(float(r[0]))) == 5)
        num_type4_tokens = sum(1 for r in data_car if int(round(float(r[0]))) == 4)

        dangerous_relations = []
        if self.input_representation == "relation":
            rel_objs = []
            for idx, r in enumerate(data_car):
                t = int(round(float(r[0])))
                if t in (4, 5):
                    continue
                rel_objs.append({
                    "idx": idx,
                    "type": t,
                    "current_clearance": float(r[1]),
                    "min_clearance": float(r[2]),
                    "closing": float(r[3]),
                    "tcpa": float(r[4]),
                    "cos_bearing": float(r[5]),
                    "sin_bearing": float(r[6]),
                })
            rel_objs.sort(key=lambda o: o["min_clearance"])
            dangerous_relations = []
            for o in rel_objs[:5]:
                raw = data_car_exact_raw[o["idx"]]
                o["raw_x"] = float(raw[1])
                o["raw_y"] = float(raw[2])
                o["raw_yaw_deg"] = float(raw[3])
                o["raw_speed_kmh"] = float(raw[4])
                o["raw_width"] = float(raw[5])
                o["raw_length"] = float(raw[6])
                dangerous_relations.append(o)

        has_lead_vehicle = False
        for r in data_car_exact_raw:
            t = int(round(float(r[0])))
            if t != 1:
                continue
            x = float(r[1])
            y = float(r[2])
            if 0.0 < x < 30.0 and abs(y) < 2.5:
                has_lead_vehicle = True
                break

        self._dbg_relation = {
            "num_type5_tokens": num_type5_tokens,
            "num_type4_tokens": num_type4_tokens,
            "dangerous_relations": dangerous_relations,
            "has_lead_vehicle": has_lead_vehicle,
        }

        # Gate 4.5B: debug-only path-relevance causal mask (env-gated, relation only)
        num_objects_before_mask = len(data_car)
        num_masked = 0
        if self.input_representation == "relation" and os.environ.get("GATE45B_MASK", "0") == "1":
            corridor_half_width = float(os.environ.get("GATE45B_CORRIDOR_HALF_WIDTH", "2.5"))
            route_pts = input_data.get("route")
            if route_pts is not None and len(route_pts) >= 2:
                route_pts = np.asarray(route_pts, dtype=np.float64)
                mask_indices = set()
                for o in dangerous_relations:
                    d_path = float(np.min(np.linalg.norm(route_pts - np.array([o["raw_x"], o["raw_y"]]), axis=-1)))
                    o["d_path"] = d_path
                    o["in_path"] = bool(d_path <= corridor_half_width)
                    o["is_lead"] = bool(
                        o["type"] == 1
                        and 0.0 < o["raw_x"] < 30.0
                        and abs(o["raw_y"]) < 2.5
                    )
                    o["masked"] = bool((not o["in_path"]) and (not o["is_lead"]))
                    if o["masked"]:
                        mask_indices.add(o["idx"])
                if mask_indices:
                    data_car = [row for i, row in enumerate(data_car) if i not in mask_indices]
                    num_masked = len(mask_indices)
                    self._dbg_relation["masked_indices"] = sorted(mask_indices)

        num_objects_after_mask = len(data_car)
        self._dbg_relation["num_dangerous"] = len(dangerous_relations)
        self._dbg_relation["num_masked"] = num_masked
        self._dbg_relation["num_objects_before_mask"] = num_objects_before_mask
        self._dbg_relation["num_objects_after_mask"] = num_objects_after_mask

        # Gate 4.5C: force-drop type=4 stop-sign token after deadlock (debug, env-gated)
        num_type4_tokens_before = num_type4_tokens
        force_clear_active = bool(
            os.environ.get("GATE45C_FORCE_DROP", "0") == "1"
            and getattr(self, "_debug_force_clear", False)
        )
        if force_clear_active:
            data_car = [r for r in data_car if int(round(float(r[0]))) != 4]
        self._dbg_relation["num_type4_tokens_before"] = num_type4_tokens_before
        self._dbg_relation["num_type4_tokens_after"] = sum(1 for r in data_car if int(round(float(r[0]))) == 4)
        self._dbg_relation["force_clear_active"] = force_clear_active
        self._dbg_relation["deadlock_detected"] = bool(getattr(self, "_dbg_deadlock", {}).get("deadlock_detected", False))
        self._dbg_relation["distance_to_stop_sign"] = getattr(self, "_dbg_deadlock", {}).get("distance_to_stop_sign", None)
        self._dbg_relation["low_speed_frames"] = getattr(self, "_dbg_deadlock", {}).get("low_speed_frames", 0)

        features = data_car

        sample['input'] = features
        sample["route_original"] = input_data["route"]
        sample["speed_limit"] = input_data["speed_limit"]
        sample["ego_speed"] = input_data["speed"]
        sample["input_ego_speed"] = input_data["speed"]

        if self.input_bev:
            sample["BEV"] = input_data["BEV"]

        # dummy data
        sample['output'] = []
        sample["waypoints"] = 0
        sample["route"] = []
        sample["target_speed"] = 0

        batch = [sample]

        input_batch = generate_batch(batch)

        return input_batch

    def _gate6_capture(self, input_batch, pred_path, pred_wps, input_data):
        """Save one complete pre-forward snapshot (npz) + metadata jsonl (5 Hz)."""
        base = os.path.join(os.path.abspath(os.getcwd()), "outputs", "gate6", "snapshots",
                            f"{self.input_representation}_{self._gate6_tag}")
        os.makedirs(base, exist_ok=True)
        frame = int(GameTime.get_frame())
        arr = {}
        for k in ("x_objs", "idxs", "route_original", "speed_limit", "BEV"):
            if k in input_batch and input_batch[k] is not None:
                arr[k] = input_batch[k].detach().cpu().numpy()
        if pred_path is not None:
            arr["pred_path_online"] = np.asarray(pred_path)
        if pred_wps is not None:
            arr["pred_wps_online"] = np.asarray(pred_wps)
        np.savez_compressed(os.path.join(base, f"f{frame:06d}.npz"), **arr)

        xobjs = arr.get("x_objs")
        actor_rows = []
        if xobjs is not None and getattr(self, "_dbg_actor_ids", None):
            ids = self._dbg_actor_ids
            for i, aid in enumerate(ids):
                if i + 1 >= xobjs.shape[0]:
                    break
                row = xobjs[i + 1]
                actor_rows.append({
                    "token_idx": i + 1,
                    "actor_id": aid,
                    "type": float(row[0]),
                    "x": float(row[1]), "y": float(row[2]),
                    "yaw_deg": float(row[3]), "speed_kmh": float(row[4]),
                    "width": float(row[5]), "length": float(row[6]),
                })
        meta = {
            "frame": frame,
            "ego_speed_mps": float(input_data["speed"]),
            "ego_pos": [float(v) for v in input_data["gps"]],
            "ego_yaw": float(input_data["yaw"]),
            "n_objects": int(xobjs.shape[0] - 1) if xobjs is not None else None,
            "actors": actor_rows,
        }
        with open(os.path.join(base, "meta.jsonl"), "a") as f:
            f.write(json.dumps(meta) + "\n")

    def destroy(self, results = None):
        super().destroy()
        del self.net