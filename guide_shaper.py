"""Semantic configuration for the non-destructive native Guide Shaper stage."""

import json
import math

import bpy
from mathutils import Vector

from . import compat


ZONE_KEYS = ("lateral", "depth", "vertical")
FALLOFFS = {"smooth", "soft", "sharp"}


def _unit(value, name):
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1.")
    return value


def _zone(value, name):
    value = value or {}
    if not isinstance(value, dict) or any(key not in ZONE_KEYS for key in value):
        raise TypeError(f"{name} must contain only lateral, depth, and vertical.")
    return {key: float(value.get(key, 0.0)) for key in ZONE_KEYS}


def stable_frame(points, surface_normal=None):
    """Return a fixed world-space frame that cannot flip along a strand."""
    if len(points) < 2:
        raise ValueError("Guide Shaper needs at least two source points.")
    along = Vector(points[1]) - Vector(points[0])
    if along.length_squared <= 1e-12:
        raise ValueError("Guide Shaper cannot derive a tangent from a duplicate root point.")
    along.normalize()
    reference = Vector(surface_normal) if surface_normal is not None else Vector((0.0, 0.0, 1.0))
    if reference.length_squared <= 1e-12:
        reference = Vector((0.0, 0.0, 1.0))
    reference.normalize()
    depth = reference - along * reference.dot(along)
    if depth.length_squared <= 1e-10:
        fallback = Vector((0.0, 0.0, 1.0))
        if abs(fallback.dot(along)) > 0.95:
            fallback = Vector((0.0, 1.0, 0.0))
        depth = fallback - along * fallback.dot(along)
    depth.normalize()
    side = along.cross(depth).normalized()
    # Re-orthogonalize so depth points toward the scalp normal/reference.
    depth = side.cross(along).normalized()
    if depth.dot(reference) < 0.0:
        side.negate()
        depth.negate()
    return {"along": along, "surface_up": reference, "side": side, "depth": depth}


def _world_offset(zone, frame):
    return (
        frame["side"] * zone["lateral"]
        + frame["depth"] * zone["depth"]
        + Vector((0.0, 0.0, 1.0)) * zone["vertical"]
    )


def curve_metrics(obj, evaluated=False):
    target = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()) if evaluated else obj
    curves = compat.native_curve_points(target, world=True)
    lengths = [sum((b - a).length for a, b in zip(points, points[1:])) for points in curves]
    roots = [points[0] for points in curves if points]
    tips = [points[-1] for points in curves if points]
    return {"curves": curves, "lengths": lengths, "roots": roots, "tips": tips}


def configure(
    obj,
    source_name,
    source_points,
    surface_normal=None,
    point_count=16,
    root_lock=1.0,
    root_zone=0.12,
    follow_surface_normal=0.0,
    lift=0.0,
    lift_zone=0.20,
    lift_falloff="smooth",
    upper=None,
    mid=None,
    lower=None,
    tip=None,
    fall=0.0,
    fall_start=0.25,
    fall_ramp="smooth",
    tip_direction=None,
    tip_release=0.0,
    tip_zone=0.20,
    smoothness=0.8,
    tension=0.45,
    preserve_shape=True,
    preserve_length=True,
    rebuild=True,
):
    point_count = int(point_count)
    if point_count < 2:
        raise ValueError("point_count must be at least 2.")
    root_lock = _unit(root_lock, "root_lock")
    root_zone = _unit(root_zone, "root_zone")
    follow_surface_normal = _unit(follow_surface_normal, "follow_surface_normal")
    lift_zone = _unit(lift_zone, "lift_zone")
    fall_start = _unit(fall_start, "fall_start")
    tip_release = _unit(tip_release, "tip_release")
    tip_zone = _unit(tip_zone, "tip_zone")
    smoothness = _unit(smoothness, "smoothness")
    tension = _unit(tension, "tension")
    for mode, name in ((lift_falloff, "lift_falloff"), (fall_ramp, "fall_ramp")):
        if mode not in FALLOFFS:
            raise ValueError(f"{name} must be one of {sorted(FALLOFFS)}.")
    zones = {name: _zone(value, name) for name, value in (
        ("upper", upper), ("mid", mid), ("lower", lower), ("tip", tip)
    )}
    tip_direction = _zone(tip_direction, "tip_direction")
    frame = stable_frame(source_points, surface_normal)
    falloff_exponents = {"soft": 0.65, "smooth": 1.0, "sharp": 1.8}
    raw_envelope_exponent = 0.65 + 1.1 * tension
    envelope_exponent = 1.0 + (raw_envelope_exponent - 1.0) * (1.0 - 0.5 * smoothness)
    # Following the surface normal blends the depth/up reference while retaining
    # the same fixed frame. It never enables Blender's unstable curve-normal field.
    lift_direction = frame["surface_up"].lerp(frame["depth"], 1.0 - follow_surface_normal)
    settings = {
        "Point Count": point_count,
        "Root Lock": root_lock,
        "Root Zone": root_zone,
        "Upper Offset": _world_offset(zones["upper"], frame),
        "Mid Offset": _world_offset(zones["mid"], frame),
        "Lower Offset": _world_offset(zones["lower"], frame),
        "Tip Offset": _world_offset(zones["tip"], frame),
        "Lift Vector": lift_direction * float(lift),
        "Lift Zone": lift_zone,
        "Fall Vector": Vector((0.0, 0.0, -float(fall))),
        "Fall Start": fall_start,
        "Tip Direction": _world_offset(tip_direction, frame),
        "Tip Release": tip_release,
        "Tip Zone": tip_zone,
        "Envelope Exponent": envelope_exponent,
        "Lift Exponent": falloff_exponents[lift_falloff],
        "Fall Exponent": falloff_exponents[fall_ramp],
        "Preserve Length": bool(preserve_length),
    }
    before = curve_metrics(obj, evaluated=False)
    modifier, applied = compat.ensure_guide_shaper_modifier(obj, settings, rebuild=rebuild)

    controls = {
        "point_count": point_count, "preserve_shape": bool(preserve_shape),
        "root_lock": root_lock, "root_zone": root_zone,
        "follow_surface_normal": follow_surface_normal, "lift": float(lift),
        "lift_zone": lift_zone, "lift_falloff": lift_falloff,
        **zones, "fall": float(fall), "fall_start": fall_start,
        "fall_ramp": fall_ramp, "tip_direction": tip_direction,
        "tip_release": tip_release, "tip_zone": tip_zone,
        "smoothness": smoothness, "tension": tension,
        "preserve_length": bool(preserve_length),
    }
    obj["hair_mcp_guide_shaper"] = True
    obj["hair_mcp_guide_shaper_source"] = source_name
    obj["hair_mcp_guide_shaper_controls"] = json.dumps(controls, sort_keys=True)
    obj["hair_mcp_guide_shaper_frame"] = json.dumps({key: list(value) for key, value in frame.items()})
    obj["hair_mcp_guide_shaper_modifier"] = modifier.name
    obj["hair_mcp_guide_shaper_preserve_length_modifier"] = ""
    bpy.context.view_layer.update()
    after = curve_metrics(obj, evaluated=True)
    root_moves = [(a - b).length for a, b in zip(after["roots"], before["roots"])]
    length_deltas = [a - b for a, b in zip(after["lengths"], before["lengths"])]
    return {
        "ok": True, "object": obj.name, "source_object": source_name,
        "shaped_object": obj.name, "point_count_before": len(source_points),
        "point_count_after": sum(len(points) for points in after["curves"]),
        "curve_count": len(after["curves"]),
        "root_position_before": list(before["roots"][0]) if before["roots"] else None,
        "root_position_after": list(after["roots"][0]) if after["roots"] else None,
        "max_root_movement": max(root_moves, default=0.0),
        "length_before": sum(before["lengths"]), "length_after": sum(after["lengths"]),
        "length_delta": sum(length_deltas), "semantic_controls": controls,
        "modifier": modifier.name, "node_group": modifier.node_group.name,
        "length_modifier": None,
        "frame_mode": "FIXED_ROOT_TANGENT_SCALP_NORMAL",
        "root_tangent": list(frame["along"]), "tip_tangent": (
            list((after["tips"][0] - after["curves"][0][-2]).normalized())
            if after["curves"] and len(after["curves"][0]) > 1 else None
        ),
        "rebuildable": True,
    }
