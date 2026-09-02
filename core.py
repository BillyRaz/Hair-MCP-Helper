import json
import math
import re
from pathlib import Path

import bpy
from mathutils import Vector

ROOT_COLLECTION = "HR_HAIR_MCP"
REGIONS_COLLECTION = "HR_REGIONS"
GUIDES_COLLECTION = "HR_GUIDES"
CHECKPOINTS_COLLECTION = "HR_CHECKPOINTS"
STATE_TEXT = "HR_MACHINE_STATE.json"
LOG_TEXT = "HR_MACHINE_LOG.txt"
COORDINATE_SPACES = {"LOCAL", "WORLD"}
SEMANTIC_KEYS = (
    "hair_mcp_role",
    "hair_mcp_region",
    "hair_mcp_group_id",
    "hair_mcp_coordinate_space",
    "hair_mcp_primary_guide",
    "hair_mcp_semantic_name",
)

DEFAULT_REGIONS = [
    "FRINGE_L", "FRINGE_R",
    "CROWN_L", "CROWN_R",
    "TEMPLE_L", "TEMPLE_R",
    "SIDE_L", "SIDE_R",
    "MIDLENGTH_L", "MIDLENGTH_R",
    "REAR_L", "REAR_R",
    "BACK_LONG", "NAPE", "FLYAWAYS",
]

CHECKPOINT_ORDER = [
    "A_SCALP_REGIONS",
    "B_PRIMARY_GUIDES",
    "C_SILHOUETTE_PART",
    "D_INTERPOLATED_GROOM",
    "E_CLUMPS_DEFORMATION",
    "F_TERTIARY_FLYAWAYS",
    "G_UNREAL_EXPORT",
]

ROLE_VALUES = {
    "SCALP", "GUIDE", "RENDER", "FLYAWAY", "PART_BOUNDARY",
    "COLLISION_PROXY", "REFERENCE", "EXPORT_HELPER",
}


def _ensure_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if col.name not in {c.name for c in parent.children}:
        # If linked somewhere else, Blender permits collection multi-linking.
        try:
            parent.children.link(col)
        except RuntimeError:
            pass
    return col


def ensure_structure():
    root = _ensure_collection(ROOT_COLLECTION)
    regions = _ensure_collection(REGIONS_COLLECTION, root)
    guides = _ensure_collection(GUIDES_COLLECTION, root)
    checkpoints = _ensure_collection(CHECKPOINTS_COLLECTION, root)
    for region in DEFAULT_REGIONS:
        _ensure_collection(f"HR_{region}", regions)
    return {
        "root": root,
        "regions": regions,
        "guides": guides,
        "checkpoints": checkpoints,
    }


def _log(message):
    text = bpy.data.texts.get(LOG_TEXT) or bpy.data.texts.new(LOG_TEXT)
    text.write(str(message).rstrip() + "\n")


def _tag(obj, role=None, region=None, group_id=None):
    obj["hair_mcp"] = True
    if role:
        if role not in ROLE_VALUES:
            raise ValueError(f"Unknown role: {role}")
        obj["hair_mcp_role"] = role
    if region:
        obj["hair_mcp_region"] = region
    if group_id is not None:
        obj["hair_mcp_group_id"] = int(group_id)
    return obj


def set_scalp(object_name=None):
    ensure_structure()
    if object_name:
        obj = bpy.data.objects.get(object_name)
    else:
        obj = bpy.context.active_object
    if obj is None:
        raise ValueError("No scalp object supplied or active.")
    if obj.type != "MESH":
        raise TypeError("Scalp must be a mesh object.")

    for other in bpy.data.objects:
        if other.get("hair_mcp_role") == "SCALP":
            other["hair_mcp_role"] = "REFERENCE"
    _tag(obj, role="SCALP", region="SCALP")
    bpy.context.scene["hair_mcp_scalp"] = obj.name
    _log(f"SCALP {obj.name}")
    return {"ok": True, "scalp": obj.name}


def get_scalp():
    name = bpy.context.scene.get("hair_mcp_scalp")
    if name and bpy.data.objects.get(name):
        return bpy.data.objects[name]
    for obj in bpy.data.objects:
        if obj.get("hair_mcp_role") == "SCALP":
            return obj
    return None


def ensure_region(name, side="CENTER", role="GUIDE", group_id=None):
    s = ensure_structure()
    clean = str(name).upper().replace(" ", "_")
    col = _ensure_collection(f"HR_{clean}", s["regions"])
    col["hair_mcp"] = True
    col["hair_mcp_region"] = clean
    col["hair_mcp_side"] = str(side).upper()
    col["hair_mcp_default_role"] = role
    if group_id is not None:
        col["hair_mcp_group_id"] = int(group_id)
    _log(f"REGION {clean} side={side} role={role}")
    return {"ok": True, "region": clean, "collection": col.name}


def _unlink_from_all_collections(obj):
    for col in list(obj.users_collection):
        col.objects.unlink(obj)


def create_poly_guides(region, guides, name_prefix=None, group_id=None, coordinate_space="WORLD"):
    """Create lightweight editable poly-curve guides from point arrays.

    guides: [ [[x,y,z], ...], [[x,y,z], ...] ]
    These are semantic primary guides, not dense render hair.
    """
    coordinate_space = _coordinate_space(coordinate_space)
    ensure_structure()
    region = str(region).upper().replace(" ", "_")
    region_result = ensure_region(region, group_id=group_id)
    region_col = bpy.data.collections[region_result["collection"]]
    prefix = name_prefix or f"HR_GUIDE_{region}"

    created = []
    for gi, points in enumerate(guides):
        if len(points) < 2:
            raise ValueError("Each guide needs at least 2 points.")
        desired_name = f"{prefix}_{gi:03d}"
        curve = bpy.data.curves.new(f"{desired_name}_DATA", type="CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 2
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for p, xyz in zip(spline.points, points):
            v = Vector(xyz)
            p.co = (*v, 1.0)

        obj = bpy.data.objects.new(desired_name, curve)
        region_col.objects.link(obj)
        _tag(obj, role="GUIDE", region=region, group_id=group_id)
        obj["hair_mcp_coordinate_space"] = coordinate_space
        obj["hair_mcp_primary_guide"] = True
        obj["hair_mcp_semantic_name"] = desired_name
        created.append(obj.name)

    _log(f"GUIDES region={region} count={len(created)}")
    return {"ok": True, "region": region, "created": created}


def tag_selected(role, region=None, group_id=None):
    objs = list(bpy.context.selected_objects)
    if not objs:
        raise ValueError("Nothing selected.")
    names = []
    for obj in objs:
        _tag(obj, role=role, region=region, group_id=group_id)
        names.append(obj.name)
    _log(f"TAG role={role} region={region} objects={','.join(names)}")
    return {"ok": True, "objects": names}


def checkpoint(name, note=""):
    ensure_structure()
    name = str(name).upper().replace(" ", "_")
    scene = bpy.context.scene
    scene["hair_mcp_checkpoint"] = name
    scene["hair_mcp_checkpoint_note"] = note
    # Store immutable-ish snapshot in a text block for MCP/human inspection.
    snap = snapshot_scene(include_validation=True)
    text_name = f"HR_CHECKPOINT_{name}.json"
    text = bpy.data.texts.get(text_name) or bpy.data.texts.new(text_name)
    text.clear()
    text.write(json.dumps(snap, indent=2))
    _log(f"CHECKPOINT {name}: {note}")
    return {"ok": True, "checkpoint": name, "text_block": text_name}


def _curve_point_count(obj):
    if obj.type == "CURVE":
        return sum(len(s.points) + len(s.bezier_points) for s in obj.data.splines)
    # New Hair Curves / CURVES data API varies by Blender version; keep safe fallback.
    if obj.type == "CURVES":
        try:
            return len(obj.data.points)
        except Exception:
            return None
    return None


def _coordinate_space(value):
    value = str(value).upper()
    if value not in COORDINATE_SPACES:
        raise ValueError(f"coordinate_space must be one of {sorted(COORDINATE_SPACES)}")
    return value


def _object(name, expected_role=None):
    obj = bpy.data.objects.get(name) if name else None
    if obj is None:
        raise ValueError(f"Object not found: {name!r}")
    if expected_role and obj.get("hair_mcp_role") != expected_role:
        raise ValueError(f"Object '{obj.name}' is not tagged as {expected_role}.")
    return obj


def _poly_spline(obj):
    if obj.type != "CURVE":
        raise TypeError(f"Guide '{obj.name}' must be a legacy CURVE object.")
    if len(obj.data.splines) != 1:
        raise ValueError(f"Guide '{obj.name}' must contain exactly one spline.")
    spline = obj.data.splines[0]
    if spline.type != "POLY" or not spline.points:
        raise ValueError(f"Guide '{obj.name}' must contain one non-empty POLY spline.")
    return spline


def _point_to_world(obj, point, coordinate_space):
    point = Vector(point)
    return obj.matrix_world @ point if coordinate_space == "LOCAL" else point


def _point_from_world(obj, point, coordinate_space):
    return obj.matrix_world.inverted() @ point if coordinate_space == "LOCAL" else Vector(point)


def _guide_points(obj, coordinate_space="WORLD"):
    coordinate_space = _coordinate_space(coordinate_space)
    points = [Vector(point.co[:3]) for point in _poly_spline(obj).points]
    if coordinate_space == "WORLD":
        points = [obj.matrix_world @ point for point in points]
    return points


def _replace_poly_points(obj, points, coordinate_space="WORLD"):
    coordinate_space = _coordinate_space(coordinate_space)
    points = [Vector(point) for point in points]
    if len(points) < 2:
        raise ValueError("A guide needs at least 2 points.")
    if not all(all(math.isfinite(value) for value in point) for point in points):
        raise ValueError("Guide points must contain only finite numbers.")
    if coordinate_space == "WORLD":
        inverse = obj.matrix_world.inverted()
        points = [inverse @ point for point in points]

    if obj.data.users > 1:
        obj.data = obj.data.copy()
    curve = obj.data
    curve.splines.clear()
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for target, point in zip(spline.points, points):
        target.co = (*point, 1.0)
    curve.update_tag()


def _semantic_metadata(obj):
    return {key: obj[key] for key in SEMANTIC_KEYS if key in obj}


def _guide_objects(object_names=None, region=None, selected=False):
    if object_names:
        candidates = [_object(name, "GUIDE") for name in object_names]
    elif selected:
        candidates = [obj for obj in bpy.context.selected_objects if obj.get("hair_mcp_role") == "GUIDE"]
    elif region:
        clean = str(region).upper().replace(" ", "_")
        candidates = [obj for obj in bpy.data.objects if obj.get("hair_mcp_role") == "GUIDE" and obj.get("hair_mcp_region") == clean]
    else:
        raise ValueError("Supply object_names, region, or selected=true.")
    unique = {obj.name: obj for obj in candidates}
    if not unique:
        raise ValueError("No semantic guides matched the request.")
    return [unique[name] for name in sorted(unique)]


def _nearest_scalp_hit(world_point):
    scalp = get_scalp()
    if scalp is None:
        raise ValueError("No scalp is set.")
    if scalp.type != "MESH":
        raise TypeError("Scalp must be a mesh object.")

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = scalp.evaluated_get(depsgraph)
    local_point = evaluated.matrix_world.inverted() @ Vector(world_point)
    ok, location, normal, face_index = evaluated.closest_point_on_mesh(local_point, depsgraph=depsgraph)
    if not ok:
        raise ValueError(f"Could not find a nearest point on scalp '{scalp.name}'.")
    world_location = evaluated.matrix_world @ location
    normal_matrix = evaluated.matrix_world.to_3x3().inverted().transposed()
    world_normal = (normal_matrix @ normal).normalized()
    return scalp, world_location, world_normal, face_index


def nearest_scalp_point(point, coordinate_space="WORLD", object_name=None):
    coordinate_space = _coordinate_space(coordinate_space)
    reference = _object(object_name) if coordinate_space == "LOCAL" else None
    world_point = _point_to_world(reference, point, coordinate_space) if reference else Vector(point)
    scalp, hit, normal, face_index = _nearest_scalp_hit(world_point)
    output = _point_from_world(reference, hit, coordinate_space) if reference else hit
    return {
        "ok": True,
        "scalp": scalp.name,
        "point": list(output),
        "coordinate_space": coordinate_space,
        "face_index": face_index,
        "distance": (hit - world_point).length,
    }


def nearest_scalp_normal(point, coordinate_space="WORLD", object_name=None):
    coordinate_space = _coordinate_space(coordinate_space)
    reference = _object(object_name) if coordinate_space == "LOCAL" else None
    world_point = _point_to_world(reference, point, coordinate_space) if reference else Vector(point)
    scalp, hit, normal, face_index = _nearest_scalp_hit(world_point)
    if reference:
        normal = (reference.matrix_world.to_3x3().transposed() @ normal).normalized()
    return {
        "ok": True,
        "scalp": scalp.name,
        "normal": list(normal),
        "coordinate_space": coordinate_space,
        "face_index": face_index,
        "nearest_point": list(_point_from_world(reference, hit, coordinate_space) if reference else hit),
    }


def read_guide_points(object_name, coordinate_space=None):
    obj = _object(object_name, "GUIDE")
    coordinate_space = _coordinate_space(coordinate_space or obj.get("hair_mcp_coordinate_space", "WORLD"))
    return {
        "ok": True,
        "object": obj.name,
        "points": [list(point) for point in _guide_points(obj, coordinate_space)],
        "coordinate_space": coordinate_space,
        "metadata": {
            "role": obj.get("hair_mcp_role"),
            "region": obj.get("hair_mcp_region"),
            "group_id": obj.get("hair_mcp_group_id"),
            "primary_guide": obj.get("hair_mcp_primary_guide"),
        },
    }


def set_guide_points(object_name, points, coordinate_space=None):
    obj = _object(object_name, "GUIDE")
    metadata = _semantic_metadata(obj)
    coordinate_space = _coordinate_space(coordinate_space or obj.get("hair_mcp_coordinate_space", "WORLD"))
    _replace_poly_points(obj, points, coordinate_space)
    for key, value in metadata.items():
        obj[key] = value
    _log(f"SET_GUIDE_POINTS object={obj.name} count={len(points)}")
    return read_guide_points(obj.name, coordinate_space)


def _root_world_position(obj):
    try:
        return _guide_points(obj, "WORLD")[0]
    except (TypeError, ValueError, IndexError):
        return None


def _nearest_scalp_distance(scalp, world_point):
    if scalp is None or world_point is None:
        return None
    try:
        _scalp, world_hit, _normal, _face_index = _nearest_scalp_hit(world_point)
    except (TypeError, ValueError, RuntimeError):
        return None
    return (world_hit - world_point).length


def root_to_scalp_distance(object_name):
    obj = _object(object_name, "GUIDE")
    root = _root_world_position(obj)
    if root is None:
        raise ValueError(f"Guide '{obj.name}' has no readable root.")
    scalp, hit, normal, face_index = _nearest_scalp_hit(root)
    return {
        "ok": True,
        "object": obj.name,
        "scalp": scalp.name,
        "distance": (hit - root).length,
        "root": list(root),
        "nearest_point": list(hit),
        "nearest_normal": list(normal),
        "face_index": face_index,
        "coordinate_space": "WORLD",
    }


def snap_guide_root(object_name):
    obj = _object(object_name, "GUIDE")
    points = _guide_points(obj, "WORLD")
    before = points[0].copy()
    _scalp, points[0], _normal, _face_index = _nearest_scalp_hit(before)
    _replace_poly_points(obj, points, "WORLD")
    distance = (points[0] - before).length
    _log(f"SNAP_GUIDE_ROOT object={obj.name} distance={distance:.9g}")
    return {"ok": True, "object": obj.name, "distance_moved": distance, "root": list(points[0])}


def snap_guide_roots(object_names=None, region=None, selected=False):
    results = [snap_guide_root(obj.name) for obj in _guide_objects(object_names, region, selected)]
    return {"ok": True, "count": len(results), "guides": results}


def _resample_points(points, count):
    count = int(count)
    if count < 2:
        raise ValueError("Resample count must be at least 2.")
    lengths = [0.0]
    for first, second in zip(points, points[1:]):
        lengths.append(lengths[-1] + (second - first).length)
    if lengths[-1] <= 1e-12:
        raise ValueError("Cannot resample a zero-length guide.")
    result = []
    segment = 0
    for index in range(count):
        target = lengths[-1] * index / (count - 1)
        while segment < len(lengths) - 2 and lengths[segment + 1] < target:
            segment += 1
        span = lengths[segment + 1] - lengths[segment]
        factor = 0.0 if span <= 1e-12 else (target - lengths[segment]) / span
        result.append(points[segment].lerp(points[segment + 1], factor))
    return result


def resample_guide(object_name, count):
    obj = _object(object_name, "GUIDE")
    points = _resample_points(_guide_points(obj, "WORLD"), count)
    _replace_poly_points(obj, points, "WORLD")
    _log(f"RESAMPLE_GUIDE object={obj.name} count={len(points)}")
    return read_guide_points(obj.name, "WORLD")


def smooth_guide(object_name, iterations=1, factor=0.5, keep_root=True, keep_tip=True):
    obj = _object(object_name, "GUIDE")
    iterations = int(iterations)
    factor = float(factor)
    if iterations < 1:
        raise ValueError("iterations must be at least 1.")
    if not 0.0 <= factor <= 1.0:
        raise ValueError("factor must be between 0 and 1.")
    points = _guide_points(obj, "WORLD")
    for _ in range(iterations):
        source = [point.copy() for point in points]
        for index in range(1, len(points) - 1):
            points[index] = source[index].lerp((source[index - 1] + source[index + 1]) * 0.5, factor)
        if not keep_root and len(points) > 1:
            points[0] = source[0].lerp(source[1], factor * 0.5)
        if not keep_tip and len(points) > 1:
            points[-1] = source[-1].lerp(source[-2], factor * 0.5)
    _replace_poly_points(obj, points, "WORLD")
    _log(f"SMOOTH_GUIDE object={obj.name} iterations={iterations} factor={factor}")
    return read_guide_points(obj.name, "WORLD")


def duplicate_guide(object_name, new_name=None):
    source = _object(object_name, "GUIDE")
    duplicate = source.copy()
    duplicate.data = source.data.copy()
    desired_name = new_name or f"{source.name}_COPY"
    duplicate.name = desired_name
    collections = list(source.users_collection)
    if not collections:
        collections = [ensure_structure()["guides"]]
    for collection in collections:
        collection.objects.link(duplicate)
    for key, value in _semantic_metadata(source).items():
        duplicate[key] = value
    duplicate["hair_mcp_semantic_name"] = desired_name
    _log(f"DUPLICATE_GUIDE source={source.name} object={duplicate.name}")
    return {"ok": True, "source": source.name, "object": duplicate.name, "metadata": _semantic_metadata(duplicate)}


def delete_guide(object_name):
    obj = _object(object_name, "GUIDE")
    name = obj.name
    curve = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if curve.users == 0:
        bpy.data.curves.remove(curve)
    _log(f"DELETE_GUIDE object={name}")
    return {"ok": True, "deleted": name}


def _semantic_name(obj):
    explicit = obj.get("hair_mcp_semantic_name")
    return str(explicit) if explicit else re.sub(r"\.\d{3}$", "", obj.name)


def _guide_geometry_issues(obj):
    issues = []
    try:
        points = _guide_points(obj, "WORLD")
    except (TypeError, ValueError) as exc:
        return [{"code": "INVALID_GUIDE_GEOMETRY", "object": obj.name, "message": str(exc)}]
    if len(points) < 2:
        issues.append({"code": "GUIDE_TOO_SHORT", "object": obj.name, "point_count": len(points)})
        return issues
    if not all(all(math.isfinite(value) for value in point) for point in points):
        issues.append({"code": "GUIDE_NONFINITE_POINT", "object": obj.name})
        return issues
    total_length = sum((second - first).length for first, second in zip(points, points[1:]))
    if total_length <= 1e-12:
        issues.append({"code": "GUIDE_ZERO_LENGTH", "object": obj.name})
    if any((second - first).length <= 1e-12 for first, second in zip(points, points[1:])):
        issues.append({"code": "GUIDE_DUPLICATE_POINTS", "object": obj.name})
    return issues


def validate_scene(root_tolerance=0.01, excessive_root_distance=0.05):
    root_tolerance = float(root_tolerance)
    excessive_root_distance = float(excessive_root_distance)
    if root_tolerance < 0.0 or excessive_root_distance < root_tolerance:
        raise ValueError("Require 0 <= root_tolerance <= excessive_root_distance.")
    issues = []
    warnings = []
    stats = {
        "guides": 0,
        "render_objects": 0,
        "flyaway_objects": 0,
        "regions": {},
    }

    scalp = get_scalp()
    if scalp is None:
        issues.append({"code": "NO_SCALP", "message": "No object is tagged as SCALP."})
    else:
        if scalp.type != "MESH":
            issues.append({"code": "SCALP_NOT_MESH", "object": scalp.name})
        if len(scalp.data.uv_layers) == 0:
            warnings.append({"code": "SCALP_NO_UV", "object": scalp.name, "message": "Scalp has no UV map; interpolation/root-UV workflows may fail."})
        if any(abs(v - 1.0) > 1e-4 for v in scalp.scale):
            warnings.append({"code": "SCALP_SCALE_UNAPPLIED", "object": scalp.name, "scale": list(scalp.scale)})

    semantic_names = {}
    for obj in bpy.data.objects:
        role = obj.get("hair_mcp_role")
        if not role:
            continue
        semantic_names.setdefault(_semantic_name(obj), []).append(obj.name)
        region = obj.get("hair_mcp_region", "UNASSIGNED")
        stats["regions"].setdefault(region, 0)
        stats["regions"][region] += 1

        if role == "GUIDE":
            stats["guides"] += 1
            if obj.type not in {"CURVE", "CURVES"}:
                issues.append({"code": "GUIDE_NOT_CURVE", "object": obj.name, "type": obj.type})
            issues.extend(_guide_geometry_issues(obj))
            root = _root_world_position(obj)
            if root is None:
                issues.append({"code": "GUIDE_ROOT_UNREADABLE", "object": obj.name})
            elif scalp:
                dist = _nearest_scalp_distance(scalp, root)
                if dist is None:
                    issues.append({"code": "ROOT_SCALP_QUERY_FAILED", "object": obj.name})
                elif dist > excessive_root_distance:
                    issues.append({
                        "code": "EXCESSIVE_ROOT_DISTANCE",
                        "object": obj.name,
                        "distance": dist,
                        "limit": excessive_root_distance,
                    })
                elif dist > root_tolerance:
                    warnings.append({
                        "code": "FLOATING_ROOT",
                        "object": obj.name,
                        "distance": dist,
                        "tolerance": root_tolerance,
                    })
        elif role == "RENDER":
            stats["render_objects"] += 1
        elif role == "FLYAWAY":
            stats["flyaway_objects"] += 1

    for semantic_name, object_names in sorted(semantic_names.items()):
        if len(object_names) > 1:
            issues.append({
                "code": "DUPLICATE_SEMANTIC_NAME",
                "semantic_name": semantic_name,
                "objects": sorted(object_names),
            })

    checkpoint_name = bpy.context.scene.get("hair_mcp_checkpoint", "NONE")
    if checkpoint_name in {"D_INTERPOLATED_GROOM", "E_CLUMPS_DEFORMATION", "F_TERTIARY_FLYAWAYS", "G_UNREAL_EXPORT"} and stats["guides"] == 0:
        issues.append({"code": "NO_GUIDES_AT_LATE_CHECKPOINT", "checkpoint": checkpoint_name})

    return {
        "ok": len(issues) == 0,
        "checkpoint": checkpoint_name,
        "issues": issues,
        "warnings": warnings,
        "stats": stats,
    }


def snapshot_scene(include_validation=False):
    scalp = get_scalp()
    items = []
    for obj in bpy.data.objects:
        if not obj.get("hair_mcp"):
            continue
        items.append({
            "name": obj.name,
            "type": obj.type,
            "role": obj.get("hair_mcp_role"),
            "region": obj.get("hair_mcp_region"),
            "group_id": obj.get("hair_mcp_group_id"),
            "coordinate_space": obj.get("hair_mcp_coordinate_space"),
            "primary_guide": obj.get("hair_mcp_primary_guide"),
            "semantic_name": _semantic_name(obj),
            "point_count": _curve_point_count(obj),
            "visible": not obj.hide_viewport,
        })
    result = {
        "protocol": "hair-mcp-helper/0.2",
        "scalp": scalp.name if scalp else None,
        "checkpoint": bpy.context.scene.get("hair_mcp_checkpoint", "NONE"),
        "checkpoint_note": bpy.context.scene.get("hair_mcp_checkpoint_note", ""),
        "objects": sorted(items, key=lambda x: x["name"]),
    }
    if include_validation:
        result["validation"] = validate_scene()
    return result


def write_machine_state():
    state = snapshot_scene(include_validation=True)
    text = bpy.data.texts.get(STATE_TEXT) or bpy.data.texts.new(STATE_TEXT)
    text.clear()
    text.write(json.dumps(state, indent=2))
    return state


def save_machine_state(path):
    state = write_machine_state()
    p = Path(bpy.path.abspath(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(p), "state": state}


def execute(command):
    if isinstance(command, str):
        command = json.loads(command)
    if not isinstance(command, dict):
        raise TypeError("Command must be a dict or JSON object string.")

    action = command.get("action")
    args = command.get("args", {}) or {}
    if not action:
        raise ValueError("Missing command.action")

    handlers = {
        "init": lambda **_: {"ok": True, "structure": {k: v.name for k, v in ensure_structure().items()}},
        "set_scalp": set_scalp,
        "nearest_scalp_point": nearest_scalp_point,
        "nearest_scalp_normal": nearest_scalp_normal,
        "root_to_scalp_distance": root_to_scalp_distance,
        "ensure_region": ensure_region,
        "create_guides": create_poly_guides,
        "read_guide_points": read_guide_points,
        "set_guide_points": set_guide_points,
        "snap_guide_root": snap_guide_root,
        "snap_guide_roots": snap_guide_roots,
        "resample_guide": resample_guide,
        "smooth_guide": smooth_guide,
        "duplicate_guide": duplicate_guide,
        "delete_guide": delete_guide,
        "tag_selected": tag_selected,
        "checkpoint": checkpoint,
        "validate": validate_scene,
        "snapshot": snapshot_scene,
        "write_state": lambda **_: write_machine_state(),
        "save_state": save_machine_state,
    }
    if action not in handlers:
        raise ValueError(f"Unknown action '{action}'. Supported: {', '.join(sorted(handlers))}")

    try:
        result = handlers[action](**args)
        if isinstance(result, dict):
            result.setdefault("action", action)
        write_machine_state()
        return result
    except Exception as exc:
        _log(f"ERROR action={action}: {exc}")
        return {"ok": False, "action": action, "error": type(exc).__name__, "message": str(exc)}

