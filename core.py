import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT_COLLECTION = "HR_HAIR_MCP"
REGIONS_COLLECTION = "HR_REGIONS"
GUIDES_COLLECTION = "HR_GUIDES"
CHECKPOINTS_COLLECTION = "HR_CHECKPOINTS"
STATE_TEXT = "HR_MACHINE_STATE.json"
LOG_TEXT = "HR_MACHINE_LOG.txt"

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
    s = ensure_structure()
    region = str(region).upper().replace(" ", "_")
    region_result = ensure_region(region, group_id=group_id)
    region_col = bpy.data.collections[region_result["collection"]]
    prefix = name_prefix or f"HR_GUIDE_{region}"

    created = []
    for gi, points in enumerate(guides):
        if len(points) < 2:
            raise ValueError("Each guide needs at least 2 points.")
        curve = bpy.data.curves.new(f"{prefix}_{gi:03d}_DATA", type="CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 2
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for p, xyz in zip(spline.points, points):
            v = Vector(xyz)
            p.co = (*v, 1.0)

        obj = bpy.data.objects.new(f"{prefix}_{gi:03d}", curve)
        region_col.objects.link(obj)
        _tag(obj, role="GUIDE", region=region, group_id=group_id)
        obj["hair_mcp_coordinate_space"] = coordinate_space
        obj["hair_mcp_primary_guide"] = True
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


def _root_world_position(obj):
    if obj.type == "CURVE" and obj.data.splines:
        s = obj.data.splines[0]
        if s.points:
            return obj.matrix_world @ Vector(s.points[0].co[:3])
        if s.bezier_points:
            return obj.matrix_world @ s.bezier_points[0].co
    return None


def _nearest_scalp_distance(scalp, world_point):
    if scalp is None or world_point is None:
        return None
    # Closest point API operates in object-local space.
    local = scalp.matrix_world.inverted() @ world_point
    ok, location, normal, face_index = scalp.closest_point_on_mesh(local)
    if not ok:
        return None
    world_hit = scalp.matrix_world @ location
    return (world_hit - world_point).length


def validate_scene(root_tolerance=0.01):
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

    seen_names = set()
    for obj in bpy.data.objects:
        if obj.name in seen_names:
            issues.append({"code": "DUPLICATE_OBJECT_NAME", "object": obj.name})
        seen_names.add(obj.name)

        role = obj.get("hair_mcp_role")
        if not role:
            continue
        region = obj.get("hair_mcp_region", "UNASSIGNED")
        stats["regions"].setdefault(region, 0)
        stats["regions"][region] += 1

        if role == "GUIDE":
            stats["guides"] += 1
            if obj.type not in {"CURVE", "CURVES"}:
                issues.append({"code": "GUIDE_NOT_CURVE", "object": obj.name, "type": obj.type})
            count = _curve_point_count(obj)
            if count is not None and count < 2:
                issues.append({"code": "GUIDE_TOO_SHORT", "object": obj.name})
            root = _root_world_position(obj)
            if scalp and root is not None:
                dist = _nearest_scalp_distance(scalp, root)
                if dist is not None and dist > float(root_tolerance):
                    warnings.append({
                        "code": "FLOATING_ROOT",
                        "object": obj.name,
                        "distance": dist,
                        "tolerance": float(root_tolerance),
                    })
        elif role == "RENDER":
            stats["render_objects"] += 1
        elif role == "FLYAWAY":
            stats["flyaway_objects"] += 1

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
            "point_count": _curve_point_count(obj),
            "visible": not obj.hide_viewport,
        })
    result = {
        "protocol": "hair-mcp-helper/0.1",
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
        "ensure_region": ensure_region,
        "create_guides": create_poly_guides,
        "tag_selected": tag_selected,
        "checkpoint": checkpoint,
        "validate": lambda **_: validate_scene(**args),
        "snapshot": lambda **_: snapshot_scene(**args),
        "write_state": lambda **_: write_machine_state(),
        "save_state": save_machine_state,
    }
    if action not in handlers:
        raise ValueError(f"Unknown action '{action}'. Supported: {', '.join(sorted(handlers))}")

    try:
        if action in {"validate", "snapshot"}:
            result = handlers[action]()
        else:
            result = handlers[action](**args)
        if isinstance(result, dict):
            result.setdefault("action", action)
        write_machine_state()
        return result
    except Exception as exc:
        _log(f"ERROR action={action}: {exc}")
        return {"ok": False, "action": action, "error": type(exc).__name__, "message": str(exc)}
