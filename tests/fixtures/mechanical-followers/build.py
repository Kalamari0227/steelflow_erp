"""Original miniature roll mechanism, exported by the pinned local Blender.

The fixture owns its generated subtree; existing T12 sources/exports are read only.
"""

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import bpy

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SPEC = importlib.util.spec_from_file_location("t12_readonly_geometry", REPO / "assets/source/build.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Existing geometry helpers unavailable")
HELPERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPERS)


def main() -> None:
    out = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("Fixture output must be new or empty")
    tool = json.loads((REPO / "assets/toolchain.json").read_text())
    if tuple(bpy.app.version) != (4, 5, 15) or HELPERS.sha(bpy.app.binary_path) != tool["executable_sha256"]:
        raise RuntimeError("Pinned Blender mismatch")
    (out / "assets/source").mkdir(parents=True)
    (out / "public/assets/steelworks/mechanical-followers").mkdir(parents=True)
    for source, target in [(REPO / "assets/toolchain.json", "assets/toolchain.json"), (HERE / "build.py", "assets/source/build.py"), (HERE / "recipe.json", "assets/source/recipe.json"), (REPO / "assets/source/LICENSE.txt", "assets/source/LICENSE.txt")]:
        shutil.copyfile(source, out / target)
    recipe = json.loads((HERE / "recipe.json").read_text())
    policy = json.loads((REPO / "shared/asset-requirements.json").read_text())
    binding = next(row for row in policy["existing_bindings"] if row["variant"] == "variant:roughing:CS-HR-03")
    asset = copy.deepcopy(json.loads((REPO / "shared/fixtures/asset-manifest-valid.json").read_text())["assets"][0])
    asset.update({"id": "fixture:mechanical-followers:CS-HR-03", "family": "hot-rolling", "kind": "roughing", "variant": binding["variant"], "requirement_ids": binding["requirement_ids"], "qa_row_ids": binding["qa_row_ids"], "placement_ids": binding["placement_ids"], "source_refs": [{"id": binding["requirement_ids"][0], "uri": "tests/fixtures/mechanical-followers/recipe.json", "note": "Synthetic miniature shared-mechanism fixture. Not a completed manufacturing asset or scheduler."}], "lods": []})
    recipe_artifact = HELPERS.artifact(out, "assets/source/recipe.json")
    def provenance(title):
        return {"origin": "self_created", "creator": recipe["author"], "title": title, "license": "project-owned", "distribution_permission": "project-local", "recipe": recipe_artifact, "third_party_inputs": []}
    driver_rest = 0.35
    rest_rotation = [math.sin(.16), 0, 0, math.cos(.16)]
    geometry_rotation = [-math.sin(.16), 0, 0, math.cos(.16)]
    clip = "miniature.roughing_roll"
    specs = [("roughing_roll", [-2, 1.8, 0], .38, None, driver_rest), ("roughing_roll_follower_1", [-2, .95, 0], .38, -1, .7), ("roughing_roll_follower_2", [.1, 1.4, 0], .76, .5, .9), ("roughing_roll_follower_3", [2.3, 1.4, 0], .76, -.5, 1.1)]
    parts = []
    for name, position, radius, ratio, rest in specs:
        ends = [0, 4 * math.pi] if ratio is None else [rest + ratio * (value - driver_rest) for value in [0, 4 * math.pi]]
        part_binding = {"type": "clip", "clock": "server_sim", "phase": "work", "progress_source": "server_phase_progress", "pause": "hold", "fault": "hold", "rest": "range_rest", "clip_id": clip} if ratio is None else {"type": "mechanical_follower", "driver_part_id": "roughing_roll", "ratio": ratio}
        parts.append({"id": name, "node_id": name, "function": "roughing_roll", "role": "operational", "motion": "rotation", "axis": [0, 0, 1], "pivot_m": position, "range": {"min": min(ends), "max": max(ends), "rest": rest, "unit": "rad"}, "binding": part_binding})
    for lod in range(3):
        model = HELPERS.Model("miniature", lod, recipe, out)
        bpy.context.scene.frame_end = 49
        model.node("roll_frame", position=(.2, .1, -.3), rotation=[0, math.sin(.2), 0, math.cos(.2)])
        model.box("support_bed", [6.4, .2, 2.2], (0, .45, 0), parent="roll_frame", material="paint", bevel=.025)
        for stand, x, height in [("left", -2, 1.8), ("middle", .1, 1.4), ("right", 2.3, 1.4)]:
            model.box(stand + "_bearing_pedestal", [.25, height - .55, .24], (x, (height + .55) / 2, -.68), parent="roll_frame", material="paint", bevel=.018)
            model.box(stand + "_bearing_foot", [.65, .08, .7], (x, .59, -.68), parent="roll_frame", material="structure", bevel=.012)
        for name, position, radius, ratio, rest in specs:
            model.node(name, "roll_frame", position, rotation=rest_rotation)
            geometry = name + "_geometry"
            model.node(geometry, name, rotation=geometry_rotation)
            model.cylinder(name + "_barrel", radius, .9, parent=geometry)
            model.box(name + "_index", [radius * .95, .09, .035], (radius * .4, 0, .47), parent=geometry, material="safety")
            model.cylinder(name + "_hub", radius * .2, 1.2, parent=geometry, material="structure")
            model.box(name + "_bearing", [.28, .28, .2], (position[0], position[1], -.68), parent="roll_frame", material="paint", bevel=.018)
            obj = model.objects[name]
            # Exporter gathers unactuated node TRS at frame 0; the approved clip starts at frame 1.
            obj.rotation_quaternion = HELPERS.quat_blender(rest_rotation)
            obj.keyframe_insert(data_path="rotation_quaternion", frame=0)
            for frame in range(1, 50):
                driver_value = (frame - 1) / 48 * 4 * math.pi
                value = driver_value if ratio is None else rest + ratio * (driver_value - driver_rest)
                displacement = value - rest
                obj.rotation_quaternion = HELPERS.quat_blender(HELPERS.quat_product([0, 0, math.sin(displacement / 2), math.cos(displacement / 2)], rest_rotation))
                obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            action = obj.animation_data.action
            action.name = name + ".authored"
            for slot in action.slots:
                for layer in action.layers:
                    for strip in layer.strips:
                        bag = strip.channelbag(slot)
                        if bag:
                            for curve in bag.fcurves:
                                for key in curve.keyframe_points:
                                    key.interpolation = "LINEAR"
        service = model.service_pad()
        model.axes()
        # Rest metadata is the authored unactuated transform; clips contain the sampled displacement.
        bpy.context.scene.frame_set(0)
        bpy.context.view_layer.update()
        if lod == 0:
            asset["nodes"] = copy.deepcopy(model.nodes)
            asset["moving_parts"] = parts
            asset["fixed_parts"] = []
            for socket in asset["sockets"]:
                socket.update({"node_id": "support_bed", "transform": {"position_m": [{"entry": -2.8, "exit": 2.8, "support": -1, "work": .7}[socket["id"]], .1, 0], "rotation_xyzw": [0, 0, 0, 1]}, "forms": ["SLAB"]})
            asset["sockets"].append(service)
            asset["materials"] = [{**row, "provenance": provenance("Miniature original " + row["id"])} for row in model.material_specs]
            asset["textures"] = [{"id": "paint_color", "artifact": HELPERS.artifact(out, "assets/source/paint.png"), "color_space": "srgb", "provenance": provenance("Original deterministic miniature paint")}]
            asset["collision_proxies"] = [{"id": "body", "node_id": "root", "shape": "box", "transform": {"position_m": [0, 1.3, 0], "rotation_xyzw": [0, 0, 0, 1]}, "size_m": [9, 5, 6], "purpose": "body", "part_id": None, "contact_socket_ids": [socket["id"] for socket in asset["sockets"]]}]
            for name, position, radius, *_ in specs:
                asset["collision_proxies"].append({"id": name + "_sweep", "node_id": "roll_frame", "shape": "box", "transform": {"position_m": position, "rotation_xyzw": [0, 0, 0, 1]}, "size_m": [radius * 2 + .04, radius * 2 + .04, 1.3], "purpose": "moving_sweep", "part_id": name, "contact_socket_ids": []})
            bpy.ops.wm.save_as_mainfile(filepath=str(out / "assets/source/miniature.blend"), check_existing=False, compress=True)
            asset["source"] = {"artifact": HELPERS.artifact(out, "assets/source/miniature.blend"), "provenance": provenance("Original editable independent miniature rolls")}
            asset["export"]["tool_artifact"] = HELPERS.artifact(out, "assets/toolchain.json")
            asset["export"]["recipe"] = HELPERS.artifact(out, "assets/source/build.py")
        relative = f"public/assets/steelworks/mechanical-followers/miniature-lod{lod}.glb"
        bpy.ops.object.select_all(action="DESELECT")
        for obj in model.objects.values():
            obj.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(out / relative), export_format="GLB", use_selection=True, export_yup=True, export_apply=True, export_extras=True, export_animations=True, export_animation_mode="ACTIVE_ACTIONS", export_nla_strips_merged_animation_name=clip, export_force_sampling=True, export_frame_range=True, export_anim_slide_to_zero=True, export_frame_step=1, export_cameras=False, export_lights=False)
        asset["lods"].append({"level": lod, "artifact": HELPERS.artifact(out, relative), "semantic_geometry_sha256": None, "nodes": copy.deepcopy(model.nodes), "socket_ids": [s["id"] for s in asset["sockets"]], "part_ids": [p["id"] for p in parts], "material_ids": [m["id"] for m in asset["materials"]]})
    HELPERS.write_json(out / "public/assets/steelworks/manifest.json", {"schema_version": 1, "purpose": "production", "assets": [asset]})
    HELPERS.write_json(out / "assets/source/inventory.json", {"external_asset_count": 0, "license": HELPERS.artifact(out, "assets/source/LICENSE.txt"), "inputs": [HELPERS.artifact(out, path) for path in ["assets/source/recipe.json", "assets/source/build.py", "assets/toolchain.json"]], "authored_assets": [asset["source"]["artifact"]], "textures": [asset["textures"][0]["artifact"]]})
    print("MINIATURE_BLENDER_EXPORT_COMPLETE", out)


if __name__ == "__main__":
    main()
