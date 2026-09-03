import json
import math
import re
from pathlib import Path

import bpy
from mathutils import Vector

from . import compat

ROOT_COLLECTION = "HR_HAIR_MCP"
REGIONS_COLLECTION = "HR_REGIONS"
GUIDES_COLLECTION = "HR_GUIDES"
CHECKPOINTS_COLLECTION = "HR_CHECKPOINTS"
NATIVE_COLLECTION = "HR_NATIVE_GUIDES"
BOUNDARIES_COLLECTION = "HR_PART_BOUNDARIES"
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
    "hair_mcp_native",
    "hair_mcp_source_guides",
    "hair_mcp_source_preserved",
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
    native = _ensure_collection(NATIVE_COLLECTION, root)
    boundaries = _ensure_collection(BOUNDARIES_COLLECTION, root)
    for region in DEFAULT_REGIONS:
        _ensure_collection(f"HR_{region}", regions)
    return {
        "root": root,
        "regions": regions,
        "guides": guides,
        "checkpoints": checkpoints,
        "native": native,
        "boundaries": boundaries,
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


def _clean_region(value):
    return str(value).upper().replace(" ", "_")


def _native_object(name):
    obj = _object(name)
    if obj.type != "CURVES" or not obj.get("hair_mcp_native"):
        raise TypeError(f"Object '{obj.name}' is not a semantic native Hair Curves object.")
    return obj


def _source_names(obj):
    value = obj.get("hair_mcp_source_guides", "[]")
    try:
        return list(json.loads(value))
    except (TypeError, ValueError):
        return []


def _link_native_object(obj, region):
    structure = ensure_structure()
    collection = _ensure_collection(f"HR_{region}", structure["regions"])
    collection.objects.link(obj)


def _remove_existing_derived(name, rebuild):
    existing = bpy.data.objects.get(name)
    if existing is None:
        return
    if not rebuild:
        raise ValueError(f"Derived object already exists: {name}")
    if existing.type != "CURVES" or not existing.get("hair_mcp_native"):
        raise ValueError(f"Refusing to replace non-derived object: {name}")
    compat.remove_native_object(existing)


def _create_native_from_sources(sources, name, keep_source=True, rebuild=True):
    if not sources:
        raise ValueError("At least one legacy guide source is required.")

    if any(
        obj.type != "CURVE" or obj.get("hair_mcp_role") != "GUIDE"
        for obj in sources
    ):
        raise TypeError(
            "Native conversion sources must be semantic legacy CURVE guides."
        )

    regions = {obj.get("hair_mcp_region") for obj in sources}

    if None in regions or len(regions) != 1:
        raise ValueError(
            "Native conversion sources must share one semantic region."
        )

    source_group_ids = []

    for source in sources:
        value = source.get("hair_mcp_group_id")

        if value is None:
            raise ValueError(
                f"Native conversion source '{source.name}' has no group_id."
            )

        source_group_ids.append(int(value))

    region = regions.pop()

    _remove_existing_derived(name, rebuild)

    native = compat.create_native_curves(
        name,
        [_guide_points(source, "WORLD") for source in sources],
    )

    _link_native_object(native, region)

    # Keep an object-level group for the legacy/single-group case only.
    unique_group_ids = sorted(set(source_group_ids))
    object_group_id = (
        unique_group_ids[0]
        if len(unique_group_ids) == 1
        else None
    )

    _tag(
        native,
        role="GUIDE",
        region=region,
        group_id=object_group_id,
    )

    native["hair_mcp_coordinate_space"] = "WORLD"
    native["hair_mcp_primary_guide"] = all(
        bool(obj.get("hair_mcp_primary_guide"))
        for obj in sources
    )
    native["hair_mcp_semantic_name"] = name
    native["hair_mcp_native"] = True
    native["hair_mcp_native_kind"] = "NATIVE_GUIDE"
    native["hair_mcp_derived"] = True
    native["hair_mcp_source_guides"] = json.dumps(
        [obj.name for obj in sources]
    )
    native["hair_mcp_source_preserved"] = bool(keep_source)
    native["hair_mcp_requested_source_preservation"] = bool(keep_source)

    # Per-curve ownership is authoritative for multi-guide native objects.
    compat.set_curve_int_attribute(
        native.data,
        "hair_mcp_group_id",
        source_group_ids,
    )

    configure_guide_group(
        native.name,
        prevent_cross_region=True,
        preserve_existing=True,
    )

    source_names = [obj.name for obj in sources]

    if not keep_source:
        for source in list(sources):
            delete_guide(source.name)

    _log(
        f"CONVERT_NATIVE object={native.name} "
        f"sources={','.join(source_names)} "
        f"groups={source_group_ids} "
        f"keep_source={keep_source}"
    )

    return {
        "ok": True,
        "object": native.name,
        "sources": source_names,
        "source_preserved": bool(keep_source),
        "curve_count": len(native.data.curves),
        "region": region,
        "group_id": object_group_id,
        "group_ids": source_group_ids,
    }


def convert_guide_to_native(object_name, new_name=None, keep_source=True, rebuild=True):
    source = _object(object_name, "GUIDE")
    name = new_name or f"{source.name}_NATIVE"
    return _create_native_from_sources([source], name, keep_source, rebuild)


def convert_region_to_native(region, new_name=None, keep_source=True, rebuild=True):
    region = _clean_region(region)
    sources = [obj for obj in _guide_objects(region=region) if obj.type == "CURVE"]
    return _create_native_from_sources(sources, new_name or f"HR_NATIVE_{region}", keep_source, rebuild)


def delete_native_hair(object_name):
    obj = _native_object(object_name)
    name = obj.name
    compat.remove_native_object(obj)
    _log(f"DELETE_NATIVE object={name}")
    return {"ok": True, "deleted": name}


def configure_guide_group(object_name, group_id=None, prevent_cross_region=True, preserve_existing=True):
    obj = _native_object(object_name)
    region = obj.get("hair_mcp_region")

    if not region:
        raise ValueError("Native guide grouping requires region metadata.")

    count = len(obj.data.curves)
    if count <= 0:
        raise ValueError("Native guide grouping requires at least one curve.")

    existing_group_ids = None

    # An explicit group_id always means "assign this group to every curve".
    # Existing per-curve ownership is preserved only when no explicit
    # override was requested.
    if group_id is not None:
        group_ids = [int(group_id)] * count

    else:
        if preserve_existing:
            try:
                attr = obj.data.attributes.get("hair_mcp_group_id")
                if attr is not None and attr.domain == 'CURVE' and len(attr.data) == count:
                    existing_group_ids = [int(item.value) for item in attr.data]
            except Exception:
                existing_group_ids = None

        if existing_group_ids is not None:
            group_ids = existing_group_ids

        else:
            resolved_group_id = obj.get("hair_mcp_group_id")

            if resolved_group_id is None:
                raise ValueError(
                    "Native guide grouping requires either existing per-curve "
                    "group IDs or an object/group_id fallback."
                )

            group_ids = [int(resolved_group_id)] * count

    compat.set_curve_int_attribute(
        obj.data,
        "hair_mcp_group_id",
        group_ids,
    )

    guide_curve_index = list(range(count))

    compat.set_curve_int_attribute(
        obj.data,
        "guide_curve_index",
        guide_curve_index,
    )

    unique_group_ids = sorted(set(group_ids))

    # Object-level group_id remains useful for the legacy/single-group case.
    # Mixed native guide objects intentionally have no single ownership group.
    if len(unique_group_ids) == 1:
        obj["hair_mcp_group_id"] = unique_group_ids[0]
    elif "hair_mcp_group_id" in obj:
        del obj["hair_mcp_group_id"]

    obj["hair_mcp_prevent_cross_region"] = bool(prevent_cross_region)

    obj["hair_mcp_guide_map"] = json.dumps({
        "region": region,
        "group_ids": group_ids,
        "guide_curve_index": guide_curve_index,
    })

    _log(
        f"GUIDE_GROUP object={obj.name} region={region} "
        f"groups={group_ids} count={count}"
    )

    return {
        "ok": True,
        "object": obj.name,
        "region": region,
        "group_id": unique_group_ids[0] if len(unique_group_ids) == 1 else None,
        "group_ids": group_ids,
        "guide_curve_index": guide_curve_index,
        "prevent_cross_region": bool(prevent_cross_region),
    }


def attach_native_to_scalp(object_name, uv_map=None, require_uv=True, add_modifier=True, rebuild=True):
    obj = _native_object(object_name)
    scalp = get_scalp()
    if scalp is None or scalp.type != "MESH":
        raise ValueError("A tagged mesh scalp is required for native attachment.")
    available_uvs = [layer.name for layer in scalp.data.uv_layers]
    uv_map = uv_map or (scalp.data.uv_layers.active.name if scalp.data.uv_layers.active else "")
    if require_uv and (not uv_map or uv_map not in available_uvs):
        raise ValueError(f"Scalp '{scalp.name}' requires a valid UV map for attachment.")
    curves = compat.native_curve_points(obj, world=True)
    distances = []
    for points in curves:
        before = points[0].copy()
        _scalp, points[0], _normal, _face_index = _nearest_scalp_hit(before)
        distances.append((points[0] - before).length)
    compat.set_native_curve_points(obj, curves)
    compat.set_attachment_surface(obj, scalp, uv_map)
    modifier_name = None
    if add_modifier:
        modifier, _settings = compat.ensure_hair_modifier(
            obj,
            "HR Attach Hair Curves to Surface",
            "Attach Hair Curves to Surface",
            {"Surface Object": scalp, "Snap to Surface": True, "Use Existing Attachment": False},
            rebuild=rebuild,
        )
        modifier_name = modifier.name
    obj["hair_mcp_attached"] = True
    obj["hair_mcp_attachment_scalp"] = scalp.name
    obj["hair_mcp_attachment_uv"] = uv_map
    obj["hair_mcp_attachment_requires_uv"] = bool(require_uv)
    _log(f"ATTACH_NATIVE object={obj.name} scalp={scalp.name} uv={uv_map}")
    return {"ok": True, "object": obj.name, "scalp": scalp.name, "uv_map": uv_map, "attached_roots": len(curves), "max_distance_moved": max(distances, default=0.0), "modifier": modifier_name}


def native_attachment_state(object_name, tolerance=1e-5):
    obj = _native_object(object_name)
    scalp = get_scalp()
    distances = []
    if scalp and scalp.type == "MESH":
        for points in compat.native_curve_points(obj, world=True):
            distances.append(_nearest_scalp_distance(scalp, points[0]))
    valid = bool(distances) and all(distance is not None and distance <= float(tolerance) for distance in distances)
    return {
        "ok": True,
        "object": obj.name,
        "declared_attached": bool(obj.get("hair_mcp_attached")),
        "surface": obj.data.surface.name if obj.data.surface else None,
        "uv_map": obj.data.surface_uv_map,
        "root_count": len(distances),
        "attached_root_count": sum(distance is not None and distance <= float(tolerance) for distance in distances),
        "max_root_distance": max((distance for distance in distances if distance is not None), default=None),
        "valid": valid,
    }


def create_part_boundary(name, points, left_region, right_region, left_group_id=None, right_group_id=None, side="CENTER", coordinate_space="WORLD"):
    coordinate_space = _coordinate_space(coordinate_space)
    if _clean_region(left_region) == _clean_region(right_region):
        raise ValueError("A part boundary must separate different regions.")
    desired_name = str(name)
    if bpy.data.objects.get(desired_name):
        raise ValueError(f"Part boundary already exists: {desired_name}")
    curve = bpy.data.curves.new(desired_name + "_DATA", type="CURVE")
    curve.dimensions = "3D"
    obj = bpy.data.objects.new(desired_name, curve)
    ensure_structure()["boundaries"].objects.link(obj)
    _tag(obj, role="PART_BOUNDARY", region="PART_BOUNDARY")
    obj["hair_mcp_semantic_name"] = desired_name
    obj["hair_mcp_coordinate_space"] = coordinate_space
    obj["hair_mcp_part_side"] = str(side).upper()
    obj["hair_mcp_left_region"] = _clean_region(left_region)
    obj["hair_mcp_right_region"] = _clean_region(right_region)
    if left_group_id is not None:
        obj["hair_mcp_left_group_id"] = int(left_group_id)
    if right_group_id is not None:
        obj["hair_mcp_right_group_id"] = int(right_group_id)
    _replace_poly_points(obj, points, coordinate_space)
    _log(f"PART_BOUNDARY object={obj.name} left={left_region} right={right_region}")
    return {"ok": True, "object": obj.name, "left_region": obj["hair_mcp_left_region"], "right_region": obj["hair_mcp_right_region"], "side": obj["hair_mcp_part_side"]}


def delete_part_boundary(object_name):
    obj = _object(object_name, "PART_BOUNDARY")
    name = obj.name
    curve = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if curve.users == 0:
        bpy.data.curves.remove(curve)
    _log(f"DELETE_PART_BOUNDARY object={name}")
    return {"ok": True, "deleted": name}


def _stage_records(obj):
    try:
        return list(json.loads(obj.get("hair_mcp_stages", "[]")))
    except (TypeError, ValueError):
        return []


def _record_stage(obj, stage, modifier, settings):
    records = [record for record in _stage_records(obj) if record.get("stage") != stage]
    records.append({"stage": stage, "modifier": modifier.name, "asset": modifier.node_group.name, "settings": settings})
    obj["hair_mcp_stages"] = json.dumps(records)


def _remove_generated_stages_from_guide(obj):
    generated_stages = {"INTERPOLATE", "CLUMP", "RESAMPLE_FLOW", "FLOW", "CURL", "STRAIGHTEN", "FRIZZ", "SMOOTH", "BLEND"}
    records = _stage_records(obj)
    for record in records:
        if record.get("stage") in generated_stages:
            modifier = obj.modifiers.get(record.get("modifier", ""))
            if modifier:
                obj.modifiers.remove(modifier)
    remaining = [record for record in records if record.get("stage") not in generated_stages]
    obj["hair_mcp_stages"] = json.dumps(remaining)
    for key in (
        "hair_mcp_interpolation",
        "hair_mcp_interpolation_density",
        "hair_mcp_interpolation_viewport_amount",
        "hair_mcp_interpolation_modifier",
    ):
        if key in obj:
            del obj[key]


def configure_interpolation(object_name, generated_name=None, density=10.0, viewport_amount=0.1, interpolation_guides=4, distance_to_guides=0.10, seed=0, part_by_mesh_islands=False, follow_surface_normal=False, rebuild=True):
    guide = _native_object(object_name)
    if not isinstance(follow_surface_normal, bool):
        raise TypeError("follow_surface_normal must be a boolean.")
    density = float(density)
    viewport_amount = float(viewport_amount)
    if density <= 0.0 or not 0.0 < viewport_amount <= 1.0:
        raise ValueError("density must be positive and viewport_amount must be in (0, 1].")
    if guide.get("hair_mcp_native_kind", "NATIVE_GUIDE") != "NATIVE_GUIDE":
        raise ValueError("Interpolation source must be a NATIVE_GUIDE object.")
    if not guide.get("hair_mcp_region"):
        raise ValueError("Interpolation requires region metadata.")

    object_group_id = guide.get("hair_mcp_group_id")
    curve_group_attr = guide.data.attributes.get("hair_mcp_group_id")

    has_curve_groups = (
        curve_group_attr is not None
        and curve_group_attr.domain == 'CURVE'
        and len(curve_group_attr.data) == len(guide.data.curves)
    )

    if object_group_id is None and not has_curve_groups:
        raise ValueError(
            "Interpolation requires either an object-level group_id "
            "or valid per-curve hair_mcp_group_id ownership."
        )
    if len(guide.data.curves) == 0:
        raise ValueError("Interpolation requires at least one native guide curve.")
    attachment = native_attachment_state(guide.name)
    if not attachment["declared_attached"] or not attachment["valid"] or not guide.data.surface:
        raise ValueError("Interpolation requires attached native guides with a valid scalp surface.")
    configure_guide_group(guide.name, prevent_cross_region=True)
    _remove_generated_stages_from_guide(guide)
    generated_name = generated_name or f"{guide.name}_GENERATED"
    existing = bpy.data.objects.get(generated_name)
    if existing:
        if not rebuild:
            raise ValueError(f"Generated Hair Curves already exists: {generated_name}")
        if existing.type != "CURVES" or existing.get("hair_mcp_native_kind") != "GENERATED_HAIR":
            raise ValueError(f"Refusing to replace non-generated object: {generated_name}")
        compat.remove_native_object(existing)
    obj = compat.copy_native_curves(generated_name, guide)
    _link_native_object(obj, guide.get("hair_mcp_region"))
    _tag(obj, role="RENDER", region=guide.get("hair_mcp_region"), group_id=guide.get("hair_mcp_group_id"))
    obj["hair_mcp_coordinate_space"] = "WORLD"
    obj["hair_mcp_semantic_name"] = generated_name
    obj["hair_mcp_native"] = True
    obj["hair_mcp_native_kind"] = "GENERATED_HAIR"
    obj["hair_mcp_derived"] = True
    obj["hair_mcp_source_native_guide"] = guide.name
    obj["hair_mcp_source_guides"] = guide.get("hair_mcp_source_guides", "[]")
    obj["hair_mcp_source_preserved"] = True
    obj["hair_mcp_attached"] = True
    obj["hair_mcp_attachment_scalp"] = guide.get("hair_mcp_attachment_scalp", "")
    obj["hair_mcp_attachment_uv"] = guide.get("hair_mcp_attachment_uv", "")
    obj["hair_mcp_attachment_requires_uv"] = guide.get("hair_mcp_attachment_requires_uv", False)
    settings = {
        "Resting Surface": True,
        "Follow Surface Normal": bool(follow_surface_normal),
        "Part by Mesh Islands": bool(part_by_mesh_islands),
        "Interpolation Guides": int(interpolation_guides),
        "Distance to Guides": float(distance_to_guides),
        "Density": density,
        "Viewport Amount": viewport_amount,
        "Seed": int(seed),
    }
    modifier, applied = compat.ensure_hair_modifier(obj, "HR Interpolate Hair Curves", "Interpolate Hair Curves", settings, rebuild=rebuild)
    obj["hair_mcp_interpolation"] = True
    obj["hair_mcp_interpolation_density"] = density
    obj["hair_mcp_interpolation_viewport_amount"] = viewport_amount
    obj["hair_mcp_interpolation_modifier"] = modifier.name
    guide["hair_mcp_generated_hair"] = obj.name
    _record_stage(obj, "INTERPOLATE", modifier, applied)
    bpy.context.view_layer.update()
    counts = compat.curve_counts(obj, evaluated=True)
    _log(f"INTERPOLATE guide={guide.name} generated={obj.name} density={density} viewport={viewport_amount}")
    return {"ok": True, "object": obj.name, "guide_object": guide.name, "modifier": modifier.name, "density": density, "viewport_amount": viewport_amount, "follow_surface_normal": bool(follow_surface_normal), "guide_count": len(guide.data.curves), "evaluated_curve_count": counts["curves"], "evaluated_point_count": counts["points"], "rebuildable": True}


def _add_groom_stage(object_name, stage, asset_name, settings, region=None, group_id=None, rebuild=True):
    obj = _native_object(object_name)
    if obj.get("hair_mcp_native_kind") != "GENERATED_HAIR":
        raise ValueError("Groom deformation stages require a GENERATED_HAIR object.")
    if region is not None and obj.get("hair_mcp_region") != _clean_region(region):
        raise ValueError("Requested region does not own the target native Hair Curves.")
    if group_id is not None and obj.get("hair_mcp_group_id") != int(group_id):
        raise ValueError("Requested group_id does not own the target native Hair Curves.")
    modifier, applied = compat.ensure_hair_modifier(obj, f"HR {asset_name}", asset_name, settings, rebuild=rebuild)
    _record_stage(obj, stage, modifier, applied)
    _log(f"GROOM_STAGE object={obj.name} stage={stage}")
    return {"ok": True, "object": obj.name, "stage": stage, "modifier": modifier.name, "settings": applied}


def add_clump(object_name, factor=0.25, shape=0.5, tip_spread=0.0, preserve_length=True, region=None, group_id=None, rebuild=True):
    return _add_groom_stage(object_name, "CLUMP", "Clump Hair Curves", {"Factor": float(factor), "Shape": float(shape), "Tip Spread": float(tip_spread), "Preserve Length": bool(preserve_length), "Existing Guide Map": True}, region, group_id, rebuild)


def configure_resample_flow(object_name, points_per_meter=24.0, region=None, group_id=None, rebuild=True):
    obj = _native_object(object_name)
    if obj.get("hair_mcp_native_kind") != "GENERATED_HAIR":
        raise ValueError("FLOW resampling requires a GENERATED_HAIR object.")
    if region is not None and obj.get("hair_mcp_region") != _clean_region(region):
        raise ValueError("Requested region does not own the target native Hair Curves.")
    if group_id is not None and obj.get("hair_mcp_group_id") != int(group_id):
        raise ValueError("Requested group_id does not own the target native Hair Curves.")
    points_per_meter = float(points_per_meter)
    if points_per_meter <= 0.0:
        raise ValueError("points_per_meter must be positive.")
    modifier, applied = compat.ensure_resample_flow_modifier(
        obj, "HR Resample for Flow", points_per_meter, rebuild=rebuild
    )
    before = compat.curve_counts_at_modifier(obj, modifier, include_modifier=False)
    after = compat.curve_counts_at_modifier(obj, modifier, include_modifier=True)
    approximate = after["points"] / after["curves"] if after["curves"] else 0.0
    _record_stage(obj, "RESAMPLE_FLOW", modifier, applied)
    _log(
        f"GROOM_STAGE object={obj.name} stage=RESAMPLE_FLOW "
        f"before={before['curves']}/{before['points']} after={after['curves']}/{after['points']}"
    )
    return {
        "ok": True, "object": obj.name, "stage": "RESAMPLE_FLOW",
        "modifier": modifier.name, "node_group": modifier.node_group.name,
        "settings": applied, "curves_before": before["curves"],
        "points_before": before["points"], "curves_after": after["curves"],
        "points_after": after["points"],
        "approximate_points_per_curve": approximate, "rebuildable": True,
    }


def add_curl(object_name, factor=0.25, radius=0.02, frequency=1.0, curl_start=0.1, seed=0, region=None, group_id=None, rebuild=True):
    return _add_groom_stage(object_name, "CURL", "Curl Hair Curves", {"Factor": float(factor), "Radius": float(radius), "Frequency": float(frequency), "Curl Start": float(curl_start), "Seed": int(seed), "Existing Guide Map": True}, region, group_id, rebuild)


def configure_flow(object_name, factor=0.025, root=0.0, upper=0.15, mid=0.55, lower=0.8, tip=0.35, wavelength=0.75, phase=0.0, variation=0.08, asymmetry=0.08, tip_release=0.35, seed=0, preserve_length=True, region=None, group_id=None, rebuild=True):
    obj = _native_object(object_name)
    if obj.get("hair_mcp_native_kind") != "GENERATED_HAIR":
        raise ValueError("FLOW requires a GENERATED_HAIR object.")
    if region is not None and obj.get("hair_mcp_region") != _clean_region(region):
        raise ValueError("Requested region does not own the target native Hair Curves.")
    if group_id is not None and obj.get("hair_mcp_group_id") != int(group_id):
        raise ValueError("Requested group_id does not own the target native Hair Curves.")
    values = (root, upper, mid, lower, tip, tip_release)
    if any(not 0.0 <= float(value) <= 1.0 for value in values):
        raise ValueError("FLOW root/upper/mid/lower/tip/tip_release must be in [0, 1].")
    if float(factor) < 0.0 or float(wavelength) <= 0.0 or float(variation) < 0.0:
        raise ValueError("FLOW factor and variation must be non-negative; wavelength must be positive.")
    settings = {
        "Factor": float(factor), "Root": float(root), "Upper": float(upper),
        "Mid": float(mid), "Lower": float(lower), "Tip": float(tip),
        "Wavelength": float(wavelength), "Phase": float(phase),
        "Variation": float(variation), "Asymmetry": float(asymmetry),
        "Tip Release": float(tip_release), "Seed": int(seed),
        "Preserve Length": bool(preserve_length),
    }
    modifier, applied = compat.ensure_flow_modifier(obj, "HR Flow Hair Curves", settings, rebuild=rebuild)
    before = compat.curve_counts_at_modifier(obj, modifier, include_modifier=False)
    after = compat.curve_counts_at_modifier(obj, modifier, include_modifier=True)
    _record_stage(obj, "FLOW", modifier, applied)
    _log(f"GROOM_STAGE object={obj.name} stage=FLOW")
    return {"ok": True, "object": obj.name, "stage": "FLOW", "modifier": modifier.name, "node_group": modifier.node_group.name, "settings": applied, "curves_before": before["curves"], "points_before": before["points"], "curves_after": after["curves"], "points_after": after["points"], "approximate_points_per_curve": (after["points"] / after["curves"] if after["curves"] else 0.0), "rebuildable": True}


def add_straighten(object_name, amount=0.25, shape=0.0, preserve_length=True, region=None, group_id=None, rebuild=True):
    return _add_groom_stage(object_name, "STRAIGHTEN", "Straighten Hair Curves", {"Amount": float(amount), "Shape": float(shape), "Preserve Length": bool(preserve_length)}, region, group_id, rebuild)


def add_frizz(object_name, factor=0.1, distance=0.005, shape=0.5, seed=0, preserve_length=True, region=None, group_id=None, rebuild=True):
    return _add_groom_stage(object_name, "FRIZZ", "Frizz Hair Curves", {"Factor": float(factor), "Distance": float(distance), "Shape": float(shape), "Seed": int(seed), "Preserve Length": bool(preserve_length)}, region, group_id, rebuild)


def add_native_smooth(object_name, amount=0.25, iterations=2, weight=0.5, lock_tips=False, preserve_length=True, region=None, group_id=None, rebuild=True):
    return _add_groom_stage(object_name, "SMOOTH", "Smooth Hair Curves", {"Amount": float(amount), "Iterations": int(iterations), "Weight": float(weight), "Lock Tips": bool(lock_tips), "Preserve Length": bool(preserve_length)}, region, group_id, rebuild)


def add_blend(object_name, factor=0.25, blend_radius=0.05, blend_neighbors=4, preserve_length=True, region=None, group_id=None, rebuild=True):
    return _add_groom_stage(object_name, "BLEND", "Blend Hair Curves", {"Factor": float(factor), "Blend Radius": float(blend_radius), "Blend Neighbors": int(blend_neighbors), "Preserve Length": bool(preserve_length)}, region, group_id, rebuild)


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
        "legacy_guides": 0,
        "native_hair_objects": 0,
        "native_hair_curves": 0,
        "native_guide_objects": 0,
        "generated_hair_objects": 0,
        "generated_hair_evaluated_curves": 0,
        "generated_hair_evaluated_points": 0,
        "attached_roots": 0,
        "unattached_roots": 0,
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
    region_groups = {}
    boundaries = []
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
            if not region or region == "UNASSIGNED":
                issues.append({"code": "GUIDE_MISSING_REGION", "object": obj.name})
            if obj.get("hair_mcp_group_id") is None:
                issues.append({"code": "GUIDE_MISSING_GROUP_ID", "object": obj.name})
            else:
                region_groups.setdefault(region, set()).add(int(obj.get("hair_mcp_group_id")))
            if obj.type == "CURVE":
                stats["legacy_guides"] += 1
                issues.extend(_guide_geometry_issues(obj))
                root = _root_world_position(obj)
                if root is None:
                    issues.append({"code": "GUIDE_ROOT_UNREADABLE", "object": obj.name})
                elif scalp:
                    dist = _nearest_scalp_distance(scalp, root)
                    if dist is None:
                        issues.append({"code": "ROOT_SCALP_QUERY_FAILED", "object": obj.name})
                    elif dist > excessive_root_distance:
                        issues.append({"code": "EXCESSIVE_ROOT_DISTANCE", "object": obj.name, "distance": dist, "limit": excessive_root_distance})
                    elif dist > root_tolerance:
                        warnings.append({"code": "FLOATING_ROOT", "object": obj.name, "distance": dist, "tolerance": root_tolerance})
            elif obj.type == "CURVES":
                kind = obj.get("hair_mcp_native_kind", "NATIVE_GUIDE")
                stats["native_hair_objects"] += 1
                stats["native_hair_curves"] += len(obj.data.curves)
                if kind == "NATIVE_GUIDE":
                    stats["native_guide_objects"] += 1
                if len(obj.data.curves) == 0 or any(curve.points_length < 2 for curve in obj.data.curves):
                    issues.append({"code": "INVALID_NATIVE_GUIDE_GEOMETRY", "object": obj.name})
                state = native_attachment_state(obj.name, tolerance=root_tolerance)
                stats["attached_roots"] += state["attached_root_count"]
                stats["unattached_roots"] += state["root_count"] - state["attached_root_count"]
                if not state["declared_attached"] or not state["valid"]:
                    issues.append({"code": "NATIVE_HAIR_NOT_ATTACHED", "object": obj.name, "attached_roots": state["attached_root_count"], "root_count": state["root_count"]})
                if obj.get("hair_mcp_attachment_requires_uv"):
                    uv_map = obj.get("hair_mcp_attachment_uv", "")
                    if not scalp or not uv_map or uv_map not in scalp.data.uv_layers:
                        issues.append({"code": "NATIVE_ATTACHMENT_INVALID_UV", "object": obj.name, "uv_map": uv_map})
                if obj.get("hair_mcp_requested_source_preservation"):
                    missing = [name for name in _source_names(obj) if bpy.data.objects.get(name) is None]
                    if missing:
                        issues.append({"code": "PRESERVED_SOURCE_MISSING", "object": obj.name, "sources": missing})
                if obj.get("hair_mcp_interpolation") and len(obj.data.curves) == 0:
                    issues.append({"code": "INTERPOLATION_WITHOUT_GUIDES", "object": obj.name})
                if obj.get("hair_mcp_interpolation") and not obj.modifiers.get(obj.get("hair_mcp_interpolation_modifier", "")):
                    issues.append({"code": "INTERPOLATION_MODIFIER_MISSING", "object": obj.name})
                if kind == "NATIVE_GUIDE" and obj.get("hair_mcp_interpolation"):
                    issues.append({"code": "INTERPOLATION_ON_NATIVE_GUIDE", "object": obj.name})
        elif role == "RENDER":
            stats["render_objects"] += 1
            if obj.type == "CURVES" and obj.get("hair_mcp_native_kind") == "GENERATED_HAIR":
                stats["native_hair_objects"] += 1
                stats["native_hair_curves"] += len(obj.data.curves)
                stats["generated_hair_objects"] += 1
                evaluated = compat.curve_counts(obj, evaluated=True)
                stats["generated_hair_evaluated_curves"] += evaluated["curves"]
                stats["generated_hair_evaluated_points"] += evaluated["points"]
                if not region or region == "UNASSIGNED" or obj.get("hair_mcp_group_id") is None:
                    issues.append({"code": "GENERATED_HAIR_MISSING_OWNERSHIP", "object": obj.name})
                source_native = bpy.data.objects.get(obj.get("hair_mcp_source_native_guide", ""))
                if not source_native or source_native.get("hair_mcp_native_kind", "NATIVE_GUIDE") != "NATIVE_GUIDE":
                    issues.append({"code": "GENERATED_HAIR_MISSING_NATIVE_GUIDE", "object": obj.name})
                state = native_attachment_state(obj.name, tolerance=root_tolerance)
                if not state["declared_attached"] or not state["valid"]:
                    issues.append({"code": "NATIVE_HAIR_NOT_ATTACHED", "object": obj.name, "attached_roots": state["attached_root_count"], "root_count": state["root_count"]})
                if obj.get("hair_mcp_interpolation") and (evaluated["curves"] == 0 or evaluated["points"] == 0):
                    issues.append({"code": "INTERPOLATION_EMPTY_OUTPUT", "object": obj.name, "evaluated_curves": evaluated["curves"], "evaluated_points": evaluated["points"]})
                if not obj.get("hair_mcp_interpolation") or not obj.modifiers.get(obj.get("hair_mcp_interpolation_modifier", "")):
                    issues.append({"code": "INTERPOLATION_MODIFIER_MISSING", "object": obj.name})
        elif role == "FLYAWAY":
            stats["flyaway_objects"] += 1
        elif role == "PART_BOUNDARY":
            boundaries.append(obj)

    for semantic_name, object_names in sorted(semantic_names.items()):
        if len(object_names) > 1:
            issues.append({
                "code": "DUPLICATE_SEMANTIC_NAME",
                "semantic_name": semantic_name,
                "objects": sorted(object_names),
            })

    for boundary in boundaries:
        left = boundary.get("hair_mcp_left_region")
        right = boundary.get("hair_mcp_right_region")
        if not left or not right or left == right:
            issues.append({"code": "INVALID_PART_BOUNDARY", "object": boundary.name})
            continue
        left_group = boundary.get("hair_mcp_left_group_id")
        right_group = boundary.get("hair_mcp_right_group_id")
        if left_group is not None and int(left_group) not in region_groups.get(left, set()):
            issues.append({"code": "PART_BOUNDARY_GROUP_CONFLICT", "object": boundary.name, "side": "LEFT", "region": left, "group_id": int(left_group)})
        if right_group is not None and int(right_group) not in region_groups.get(right, set()):
            issues.append({"code": "PART_BOUNDARY_GROUP_CONFLICT", "object": boundary.name, "side": "RIGHT", "region": right, "group_id": int(right_group)})
        if left_group is not None and right_group is not None and int(left_group) == int(right_group):
            issues.append({"code": "PART_BOUNDARY_SHARED_GROUP", "object": boundary.name, "group_id": int(left_group)})

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
        item = {
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
        }
        if obj.type == "CURVES" and obj.get("hair_mcp_native"):
            attachment = native_attachment_state(obj.name)
            original_counts = compat.curve_counts(obj, evaluated=False)
            evaluated_counts = compat.curve_counts(obj, evaluated=True)
            item.update({
                "native": True,
                "native_kind": obj.get("hair_mcp_native_kind", "NATIVE_GUIDE"),
                "curve_count": len(obj.data.curves),
                "original_counts": original_counts,
                "evaluated_counts": evaluated_counts,
                "source_guides": _source_names(obj),
                "source_native_guide": obj.get("hair_mcp_source_native_guide"),
                "source_preserved": obj.get("hair_mcp_source_preserved"),
                "attachment": attachment,
                "guide_group_id": compat.get_curve_int_attribute(obj.data, "hair_mcp_group_id"),
                "guide_curve_index": compat.get_curve_int_attribute(obj.data, "guide_curve_index"),
                "interpolation": {
                    "enabled": bool(obj.get("hair_mcp_interpolation")),
                    "modifier": obj.get("hair_mcp_interpolation_modifier"),
                    "density": obj.get("hair_mcp_interpolation_density"),
                    "viewport_amount": obj.get("hair_mcp_interpolation_viewport_amount"),
                },
                "stages": _stage_records(obj),
            })
        elif obj.get("hair_mcp_role") == "PART_BOUNDARY":
            item["part_boundary"] = {
                "side": obj.get("hair_mcp_part_side"),
                "left_region": obj.get("hair_mcp_left_region"),
                "right_region": obj.get("hair_mcp_right_region"),
                "left_group_id": obj.get("hair_mcp_left_group_id"),
                "right_group_id": obj.get("hair_mcp_right_group_id"),
            }
        items.append(item)
    result = {
        "protocol": "hair-mcp-helper/0.3",
        "capabilities": {"native_hair_curves": compat.supports_native_hair(), "blender_version": list(compat.blender_version())},
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

    # Imported lazily to avoid a core <-> styler import cycle at module load.
    from . import styler

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
        "convert_guide_to_native": convert_guide_to_native,
        "convert_region_to_native": convert_region_to_native,
        "delete_native_hair": delete_native_hair,
        "configure_guide_group": configure_guide_group,
        "attach_native_to_scalp": attach_native_to_scalp,
        "native_attachment_state": native_attachment_state,
        "create_part_boundary": create_part_boundary,
        "delete_part_boundary": delete_part_boundary,
        "configure_interpolation": configure_interpolation,
        "add_clump": add_clump,
        "configure_resample_flow": configure_resample_flow,
        "add_curl": add_curl,
        "configure_flow": configure_flow,
        "add_straighten": add_straighten,
        "add_frizz": add_frizz,
        "add_native_smooth": add_native_smooth,
        "add_blend": add_blend,
        "style_capabilities": lambda **_: styler.capabilities(),
        "style_plan": styler.plan_style,
        "style_apply": styler.apply_style,
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
        # Discovery and planning are strictly read-only. A style dry-run must
        # not even update Blender Text datablocks.
        if action not in {"style_capabilities", "style_plan"}:
            write_machine_state()
        return result
    except Exception as exc:
        _log(f"ERROR action={action}: {exc}")
        return {"ok": False, "action": action, "error": type(exc).__name__, "message": str(exc)}
