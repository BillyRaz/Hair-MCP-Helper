"""Semantic hairstyle profiles over Hair MCP Helper's existing native operations.

This module plans and orchestrates work.  Geometry remains the responsibility of
Blender Hair Curves and Blender's bundled Geometry Nodes hair assets.
"""

from copy import deepcopy
import inspect

import bpy

from . import compat, core


STAGE_ORDER = (
    "interpolation", "clump", "resample_flow", "flow", "curl", "straighten", "smooth", "blend", "frizz"
)
STAGE_FUNCTIONS = {
    "interpolation": core.configure_interpolation,
    "clump": core.add_clump,
    "resample_flow": core.configure_resample_flow,
    "flow": core.configure_flow,
    "curl": core.add_curl,
    "straighten": core.add_straighten,
    "smooth": core.add_native_smooth,
    "blend": core.add_blend,
    "frizz": core.add_frizz,
}
REGION_META_KEYS = {"enabled", "notes"}
PROFILE_KEYS = {"id", "description", "defaults", "regions", "warnings"}


# Conservative starting values, not artist-approved final grooming values.
ARII_V1 = {
    "id": "RAZ_ARII_HAIR_V1",
    "description": "Long polished near-black ARII groom; broad S-flow and calm roots.",
    "defaults": {
        "interpolation": {
            "density": 10.0, "viewport_amount": 0.1,
            "interpolation_guides": 1, "distance_to_guides": 0.10,
            "seed": 0, "part_by_mesh_islands": False,
        },
        "clump": {"factor": 0.25, "shape": 0.55, "tip_spread": 0.02, "preserve_length": True},
        "flow": {"factor": 0.025, "root": 0.0, "upper": 0.12, "mid": 0.48, "lower": 0.72, "tip": 0.3, "wavelength": 0.8, "phase": 0.0, "variation": 0.07, "asymmetry": 0.06, "tip_release": 0.4, "seed": 0, "preserve_length": True},
        "curl": {"factor": 0.18, "radius": 0.035, "frequency": 0.65, "curl_start": 0.25, "seed": 0},
        "smooth": {"amount": 0.25, "iterations": 2, "weight": 0.5, "lock_tips": False, "preserve_length": True},
        "frizz": {"factor": 0.02, "distance": 0.002, "shape": 0.65, "seed": 0, "preserve_length": True},
    },
    "regions": {
        "HAIRLINE": {"interpolation": {"distance_to_guides": 0.05}, "smooth": {"amount": 0.3}},
        "PART_L": {"interpolation": {"distance_to_guides": 0.05}, "smooth": {"amount": 0.35}},
        "PART_R": {"interpolation": {"distance_to_guides": 0.05}, "smooth": {"amount": 0.35}},
        "TOP_L": {"interpolation": {}, "clump": {"factor": 0.18}, "smooth": {"amount": 0.32}},
        "TOP_R": {"interpolation": {}, "clump": {"factor": 0.19}, "smooth": {"amount": 0.31}},
        "CROWN": {"interpolation": {}, "clump": {"factor": 0.18}, "smooth": {"amount": 0.38}},
        "FACEFRAME_L": {"interpolation": {"distance_to_guides": 0.06}, "clump": {"factor": 0.3}, "flow": {"factor": 0.028, "mid": 0.55, "lower": 0.78, "phase": 0.2, "seed": 17}, "curl": {"factor": 0.12, "radius": 0.045, "frequency": 0.55, "curl_start": 0.38, "seed": 17}, "smooth": {"amount": 0.3}, "frizz": {"factor": 0.01}},
        "FACEFRAME_R": {"interpolation": {"distance_to_guides": 0.06}, "clump": {"factor": 0.28}, "flow": {"factor": 0.027, "mid": 0.53, "lower": 0.76, "phase": -0.15, "seed": 29}, "curl": {"factor": 0.11, "radius": 0.047, "frequency": 0.52, "curl_start": 0.4, "seed": 29}, "smooth": {"amount": 0.29}, "frizz": {"factor": 0.01}},
        "TEMPLE_L": {"interpolation": {"distance_to_guides": 0.07}, "clump": {"factor": 0.22}, "smooth": {}},
        "TEMPLE_R": {"interpolation": {"distance_to_guides": 0.07}, "clump": {"factor": 0.21}, "smooth": {}},
        "SIDE_L": {"interpolation": {"distance_to_guides": 0.10}, "clump": {"factor": 0.3}, "flow": {"factor": 0.03, "upper": 0.1, "mid": 0.5, "lower": 0.82, "tip": 0.28, "wavelength": 0.82, "variation": 0.06, "asymmetry": 0.07, "tip_release": 0.45, "seed": 41}, "curl": {"factor": 0.08, "seed": 41}, "smooth": {}, "frizz": {}},
        "SIDE_R": {"interpolation": {"distance_to_guides": 0.10}, "clump": {"factor": 0.29}, "flow": {"factor": 0.029, "upper": 0.1, "mid": 0.48, "lower": 0.8, "tip": 0.28, "wavelength": 0.84, "variation": 0.06, "asymmetry": -0.07, "tip_release": 0.45, "seed": 53}, "curl": {"factor": 0.08, "seed": 53}, "smooth": {}, "frizz": {}},
        "BACK_UPPER": {"interpolation": {"distance_to_guides": 0.11}, "clump": {"factor": 0.24}, "flow": {"factor": 0.018, "mid": 0.4, "lower": 0.62, "seed": 61}, "smooth": {"amount": 0.35}},
        "BACK_MID": {"interpolation": {"distance_to_guides": 0.12}, "clump": {"factor": 0.32}, "flow": {"factor": 0.028, "mid": 0.52, "lower": 0.8, "seed": 67}, "curl": {"factor": 0.08, "radius": 0.045, "seed": 67}, "smooth": {}},
        "BACK_LOWER": {"interpolation": {"distance_to_guides": 0.12}, "clump": {"factor": 0.3, "tip_spread": 0.04}, "flow": {"factor": 0.032, "mid": 0.55, "lower": 0.85, "tip": 0.32, "wavelength": 0.88, "tip_release": 0.48, "seed": 79}, "curl": {"factor": 0.1, "radius": 0.05, "curl_start": 0.35, "seed": 79}, "smooth": {"amount": 0.2}, "frizz": {}},
        "NAPE": {"interpolation": {"distance_to_guides": 0.08}, "clump": {"factor": 0.2}, "smooth": {}},
        "SURFACE_BREAKUP": {"interpolation": {"density": 3.0, "viewport_amount": 0.05, "distance_to_guides": 0.07}, "clump": {"factor": 0.16}, "curl": {"factor": 0.14, "seed": 97}, "frizz": {"factor": 0.025}},
        "FLYAWAYS": {"enabled": False, "notes": "Tertiary pass only; never auto-applied with the primary groom."},
    },
    "warnings": [
        "Preset values are conservative starting points and require character-scale/artist review.",
        "FLOW uses the native curve normal; unusual or unstable curve tilt can change its side direction.",
        "FLOW preserve_length is advisory in V0.2 because Set Position has no native exact-length constraint.",
        "Hair color, simulation, flyaway creation, and Unreal export are outside Styler V0.2.",
    ],
}

BUILTIN_PROFILES = {ARII_V1["id"]: ARII_V1}


def capabilities():
    return {
        "protocol": "hair-mcp-styler/0.3",
        "supported_stages": list(STAGE_ORDER),
        "profile_keys": sorted(PROFILE_KEYS),
        "region_keys": list(STAGE_ORDER) + sorted(REGION_META_KEYS),
        "dry_run": True,
        "built_in_profiles": sorted(BUILTIN_PROFILES),
        "semantics": {
            "distance_to_guides": "Spatial guide-root locality radius in meters; not density.",
            "density": "Generated strand/sample quantity.",
            "viewport_amount": "Viewport sampling/visibility and performance control.",
            "interpolation_guides": "Guide shapes used by Blender; 1 is strict local ownership, >1 intentionally blends shapes.",
            "follow_surface_normal": "Rotate interpolated children from guide-up toward their scalp-root normals. False preserves coherent translated guide shape.",
            "group_ownership": "Per-curve hair_mcp_group_id is authoritative when object-level ownership is absent.",
            "missing_stage": "Not applied; defaults only fill parameters for explicitly declared region stages.",
            "flow": "Broad strand-length directional shaping using a smooth root-to-tip envelope; intended for hairstyle silhouette, not small curls or frizz.",
            "points_per_meter": "Length-aware deformation resolution applied to generated Hair Curves immediately before FLOW.",
        },
        "engine_boundary": "Styler calls HMH core; Blender native Hair Curves/assets produce geometry.",
        "known_limitations": [
            "FLOW direction follows Blender's native curve normal, so unstable curve tilt can rotate the flow plane.",
            "FLOW preserve_length is advisory in V0.2; native Set Position does not enforce exact arc length.",
        ],
    }


def get_profile(profile):
    if isinstance(profile, str):
        if profile not in BUILTIN_PROFILES:
            raise ValueError(f"Unknown style profile '{profile}'.")
        return deepcopy(BUILTIN_PROFILES[profile])
    if not isinstance(profile, dict):
        raise TypeError("profile must be a profile dict or built-in profile id.")
    return deepcopy(profile)


def _allowed_parameters(stage):
    ignored = {"object_name", "region", "group_id", "rebuild"}
    return set(inspect.signature(STAGE_FUNCTIONS[stage]).parameters) - ignored


def validate_profile(profile):
    errors = []
    try:
        value = get_profile(profile)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    unknown_profile = set(value) - PROFILE_KEYS
    if unknown_profile:
        errors.append(f"Unknown profile keys: {sorted(unknown_profile)}")
    if not isinstance(value.get("id"), str) or not value.get("id", "").strip():
        errors.append("Profile id must be a non-empty string.")
    defaults = value.get("defaults", {})
    regions = value.get("regions")
    if not isinstance(defaults, dict):
        errors.append("defaults must be a dictionary.")
        defaults = {}
    if not isinstance(regions, dict):
        errors.append("regions must be a dictionary.")
        regions = {}
    unknown_defaults = set(defaults) - set(STAGE_ORDER)
    if unknown_defaults:
        errors.append(f"Unknown default stages: {sorted(unknown_defaults)}")
    for stage, params in defaults.items():
        if stage in STAGE_ORDER and not isinstance(params, dict):
            errors.append(f"Default stage {stage} must be a dictionary.")
        elif stage in STAGE_ORDER:
            unsupported = set(params) - _allowed_parameters(stage)
            if unsupported:
                errors.append(f"Default stage {stage} has unsupported parameters: {sorted(unsupported)}")
    for region, settings in regions.items():
        if not isinstance(settings, dict):
            errors.append(f"Region {region} must be a dictionary.")
            continue
        if "enabled" in settings and not isinstance(settings["enabled"], bool):
            errors.append(f"Region {region}.enabled must be a boolean.")
        unknown = set(settings) - set(STAGE_ORDER) - REGION_META_KEYS
        if unknown:
            errors.append(f"Region {region} has unknown stages/keys: {sorted(unknown)}")
        for stage in STAGE_ORDER:
            if stage not in settings:
                continue
            params = settings[stage]
            if not isinstance(params, dict):
                errors.append(f"Region {region}.{stage} must be a dictionary.")
                continue
            default_params = defaults.get(stage, {})
            if not isinstance(default_params, dict):
                continue
            merged = dict(default_params)
            merged.update(params)
            unsupported = set(merged) - _allowed_parameters(stage)
            if unsupported:
                errors.append(f"Region {region}.{stage} has unsupported parameters: {sorted(unsupported)}")
            if stage == "interpolation":
                try:
                    if not isinstance(merged.get("follow_surface_normal", False), bool):
                        errors.append(f"Region {region}: follow_surface_normal must be a boolean.")
                    guides = merged.get("interpolation_guides", 1)
                    if isinstance(guides, bool) or int(guides) != guides or guides < 1:
                        errors.append(f"Region {region}: interpolation_guides must be an integer >= 1.")
                    if float(merged.get("distance_to_guides", 0.10)) <= 0:
                        errors.append(f"Region {region}: distance_to_guides must be positive.")
                    if float(merged.get("density", 10.0)) <= 0:
                        errors.append(f"Region {region}: density must be positive.")
                    viewport = float(merged.get("viewport_amount", 0.1))
                    if not 0 < viewport <= 1:
                        errors.append(f"Region {region}: viewport_amount must be in (0, 1].")
                except (TypeError, ValueError):
                    errors.append(f"Region {region}: interpolation controls must be numeric.")
            elif stage == "resample_flow":
                try:
                    if float(merged.get("points_per_meter", 24.0)) <= 0.0:
                        errors.append(f"Region {region}: resample_flow.points_per_meter must be positive.")
                except (TypeError, ValueError):
                    errors.append(f"Region {region}: resample_flow.points_per_meter must be numeric.")
            elif stage == "flow":
                try:
                    for name in ("root", "upper", "mid", "lower", "tip", "tip_release"):
                        if not 0.0 <= float(merged.get(name, 0.0)) <= 1.0:
                            errors.append(f"Region {region}: flow.{name} must be in [0, 1].")
                    if float(merged.get("factor", 0.0)) < 0.0 or float(merged.get("variation", 0.0)) < 0.0:
                        errors.append(f"Region {region}: flow factor and variation must be non-negative.")
                    if float(merged.get("wavelength", 0.0)) <= 0.0:
                        errors.append(f"Region {region}: flow wavelength must be positive.")
                except (TypeError, ValueError):
                    errors.append(f"Region {region}: flow controls must be numeric.")
    return {"ok": not errors, "style_id": value.get("id"), "errors": errors, "warnings": list(value.get("warnings", []))}


def _region_objects(region):
    clean = str(region).upper().replace(" ", "_")
    guides, generated = [], []
    for obj in bpy.data.objects:
        if obj.type != "CURVES" or obj.get("hair_mcp_region") != clean:
            continue
        kind = obj.get("hair_mcp_native_kind")
        if kind == "NATIVE_GUIDE":
            guides.append(obj)
        elif kind == "GENERATED_HAIR":
            generated.append(obj)
    return sorted(guides, key=lambda obj: obj.name), sorted(generated, key=lambda obj: obj.name)


def _ownership(obj):
    per_curve = compat.get_curve_int_attribute(obj.data, "hair_mcp_group_id")
    object_group = obj.get("hair_mcp_group_id")
    return {
        "mode": "per_curve" if object_group is None and per_curve is not None else "object",
        "object_group_id": object_group,
        "curve_group_ids": sorted(set(per_curve)) if per_curve is not None else None,
    }


def plan_style(profile="RAZ_ARII_HAIR_V1", regions=None, rebuild=True):
    value = get_profile(profile)
    validation = validate_profile(value)
    if not validation["ok"]:
        return {"ok": False, "style_id": value.get("id"), "errors": validation["errors"], "warnings": validation["warnings"]}
    selected = {str(item).upper().replace(" ", "_") for item in regions} if regions else None
    plans, skipped, missing, warnings = [], [], [], list(validation["warnings"])
    defaults = value.get("defaults", {})
    for raw_region, region_settings in value["regions"].items():
        region = str(raw_region).upper().replace(" ", "_")
        if selected is not None and region not in selected:
            continue
        if region_settings.get("enabled", True) is False:
            skipped.append({"region": region, "reason": "disabled", "notes": region_settings.get("notes")})
            continue
        stages = []
        for stage in STAGE_ORDER:
            if stage in region_settings:
                params = dict(defaults.get(stage, {}))
                params.update(region_settings[stage])
                params["rebuild"] = bool(rebuild)
                stages.append({"stage": stage, "parameters": params})
        guides, generated = _region_objects(region)
        if not guides and not generated:
            missing.append({"region": region, "needs": "NATIVE_GUIDE and/or GENERATED_HAIR"})
            continue
        if "interpolation" in region_settings and not guides:
            warnings.append(f"Region {region} declares interpolation but has no NATIVE_GUIDE target.")
        plans.append({
            "region": region,
            "native_guides": [{"object": obj.name, "ownership": _ownership(obj)} for obj in guides],
            "generated_hair": [obj.name for obj in generated],
            "stages": stages,
        })
    if selected is not None:
        undeclared = selected - {str(name).upper().replace(" ", "_") for name in value["regions"]}
        skipped.extend({"region": name, "reason": "not_declared_in_profile"} for name in sorted(undeclared))
    return {"ok": True, "dry_run": True, "style_id": value["id"], "resolved_regions": plans, "skipped_regions": skipped, "missing_targets": missing, "warnings": warnings}


def apply_style(profile="RAZ_ARII_HAIR_V1", regions=None, rebuild=True):
    plan = plan_style(profile, regions=regions, rebuild=rebuild)
    if not plan.get("ok"):
        return plan
    results, errors, empty_interpolations = [], [], []
    for region_plan in plan["resolved_regions"]:
        region = region_plan["region"]
        generated_names = list(region_plan["generated_hair"])
        region_had_empty_interpolation = False
        for stage_plan in region_plan["stages"]:
            stage = stage_plan["stage"]
            params = dict(stage_plan["parameters"])
            if stage == "interpolation":
                generated_names = []
                for guide in region_plan["native_guides"]:
                    try:
                        result = core.configure_interpolation(guide["object"], **params)
                        results.append({"region": region, "stage": stage, "result": result})
                        if result.get("evaluated_curve_count", 0) > 0:
                            generated_names.append(result["object"])
                        else:
                            region_had_empty_interpolation = True
                            empty_interpolations.append({"region": region, "stage": stage, "object": result["object"], "guide_object": guide["object"], "error": "EmptyInterpolation", "message": "Interpolation completed structurally but evaluated to zero curves; dependent stages were skipped for this target."})
                    except Exception as exc:
                        errors.append({"region": region, "stage": stage, "object": guide["object"], "error": type(exc).__name__, "message": str(exc)})
                continue
            if not generated_names:
                if not region_had_empty_interpolation:
                    errors.append({"region": region, "stage": stage, "error": "MissingTarget", "message": "No generated hair exists; interpolation did not produce a target."})
                continue
            for object_name in generated_names:
                try:
                    result = STAGE_FUNCTIONS[stage](object_name, region=region, **params)
                    results.append({"region": region, "stage": stage, "result": result})
                except Exception as exc:
                    errors.append({"region": region, "stage": stage, "object": object_name, "error": type(exc).__name__, "message": str(exc)})
    core._log(f"STYLE_APPLY style={plan['style_id']} actions={len(results)} errors={len(errors)}")
    return {"ok": not errors, "style_id": plan["style_id"], "applied": results, "errors": errors, "empty_interpolations": empty_interpolations, "skipped_regions": plan["skipped_regions"], "missing_targets": plan["missing_targets"], "warnings": plan["warnings"], "rebuildable": True}
