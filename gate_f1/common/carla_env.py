"""CARLA boot/cleanup/spawn helpers shared by F1 smoke + scenario runners."""
import random

import carla


def connect(host="localhost", port=2000, town="Town12", timeout=120):
    client = carla.Client(host, port)
    client.set_timeout(timeout)
    world = client.get_world()
    if world.get_map().name.split("/")[-1] != town:
        world = client.load_world(town)
    for _ in range(10):
        world.wait_for_tick()
    world.set_weather(carla.WeatherParameters.ClearNoon)
    world.apply_settings(carla.WorldSettings(synchronous_mode=False))
    for _ in range(5):
        world.wait_for_tick()
    return client, world


def clear_dynamic(world):
    for actor in list(world.get_actors().filter("*vehicle*")) + \
                  list(world.get_actors().filter("*walker*")):
        try:
            if actor.is_alive:
                actor.destroy()
        except Exception:
            pass
    for _ in range(5):
        world.wait_for_tick()


def spawn_vehicle(world, bp_name, x, y, z, yaw, hero=False, tries=3):
    lib = world.get_blueprint_library()
    for name in (bp_name,) if bp_name else ("vehicle.tesla.model3", "vehicle.mini.cooper_s",
                                            "vehicle.dodge.charger_police", "vehicle.audi.tt",
                                            "vehicle.lincoln.mkz_2020"):
        bps = lib.filter(name)
        if not bps:
            continue
        bp = bps[0]
        if hero:
            bp.set_attribute("role_name", "hero")
        for _ in range(tries):
            a = world.try_spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw)))
            if a is not None:
                return a
    return None


def spawn_walker(world, x, y, z, tries=4, bpname="walker.pedestrian.0002"):
    lib = world.get_blueprint_library()
    bp = lib.filter(bpname)[0]
    for _ in range(tries):
        a = world.try_spawn_actor(bp, carla.Transform(
            carla.Location(x=x, y=y, z=z)))
        if a is not None:
            return a
    return None


def hold_transform(actor, x, y, yaw):
    t = actor.get_transform()
    actor.set_transform(carla.Transform(
        carla.Location(x=x, y=y, z=t.location.z),
        carla.Rotation(yaw=yaw if yaw is not None else t.rotation.yaw)))
    actor.set_target_velocity(carla.Vector3D(0, 0, 0))
