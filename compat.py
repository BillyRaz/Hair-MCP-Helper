"""Version-sensitive Blender Hair Curves and node-asset helpers."""

import os

import bpy
from mathutils import Vector


HAIR_ASSET_FILE = "procedural_hair_node_assets.blend"
FLOW_NODE_GROUP = "HMH Flow Hair Curves V0.2"
RESAMPLE_FLOW_NODE_GROUP = "HMH Resample for Flow V0.3"
GUIDE_SHAPER_NODE_GROUP = "HMH Guide Shaper V0.1"
SOCKET_ALIASES = {
    "Surface Object": ("Surface",),
    "Use Existing Attachment": ("Sample Attachment UV",),
    "Resting Surface": ("Surface Rest Position",),
}


def blender_version():
    return tuple(bpy.app.version[:3])


def supports_native_hair():
    return hasattr(bpy.data, "hair_curves")


def require_native_hair():
    if not supports_native_hair():
        raise RuntimeError("Native Hair Curves require a Blender version exposing bpy.data.hair_curves.")


def create_native_curves(name, curves_world):
    """Create one native Hair Curves object from world-space point arrays."""
    require_native_hair()
    sizes = [len(points) for points in curves_world]
    if not sizes or any(size < 2 for size in sizes):
        raise ValueError("Native conversion requires at least one curve with two points.")
    data = bpy.data.hair_curves.new(name + "_DATA")
    data.add_curves(sizes)
    flat = [float(value) for points in curves_world for point in points for value in Vector(point)]
    data.attributes["position"].data.foreach_set("vector", flat)
    data.update_tag()
    return bpy.data.objects.new(name, data)


def copy_native_curves(name, source):
    if source.type != "CURVES":
        raise TypeError(f"Object '{source.name}' is not native Hair Curves.")
    return bpy.data.objects.new(name, source.data.copy())


def copy_evaluated_native_curves(name, source):
    if source.type != "CURVES":
        raise TypeError(f"Object '{source.name}' is not native Hair Curves.")

    states = [
        (modifier, modifier.show_viewport, modifier.show_render)
        for modifier in source.modifiers
    ]

    try:
        # Materialize attachment state only.
        for modifier in source.modifiers:
            keep = "Attach Hair Curves" in modifier.name
            modifier.show_viewport = keep
            modifier.show_render = keep

        bpy.context.view_layer.update()

        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = source.evaluated_get(depsgraph)

        data = evaluated.data.copy()
        result = bpy.data.objects.new(name, data)
        result.matrix_world = source.matrix_world.copy()

        return result

    finally:
        for modifier, viewport, render in states:
            modifier.show_viewport = viewport
            modifier.show_render = render

        bpy.context.view_layer.update()


def curve_counts(obj, evaluated=False):
    target = obj
    if evaluated:
        target = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = getattr(target, "data", None)
    if target.type != "CURVES" or data is None:
        return {"curves": 0, "points": 0}
    return {"curves": len(data.curves), "points": len(data.points)}


def curve_counts_at_modifier(obj, modifier, include_modifier=True):
    """Count evaluated curves/points immediately before or after a modifier."""
    states = [(item, item.show_viewport, item.show_render) for item in obj.modifiers]
    try:
        reached = False
        for item in obj.modifiers:
            if item == modifier:
                reached = True
                item.show_viewport = bool(include_modifier)
                item.show_render = bool(include_modifier)
            elif reached:
                item.show_viewport = False
                item.show_render = False
        bpy.context.view_layer.update()
        return curve_counts(obj, evaluated=True)
    finally:
        for item, viewport, render in states:
            item.show_viewport = viewport
            item.show_render = render
        bpy.context.view_layer.update()


def native_curve_points(obj, world=True):
    if obj.type != "CURVES":
        raise TypeError(f"Object '{obj.name}' is not native Hair Curves.")
    result = []
    for curve in obj.data.curves:
        points = [Vector(point.position) for point in curve.points]
        if world:
            points = [obj.matrix_world @ point for point in points]
        result.append(points)
    return result


def set_native_curve_points(obj, curves_world):
    if obj.type != "CURVES":
        raise TypeError(f"Object '{obj.name}' is not native Hair Curves.")
    sizes = [len(points) for points in curves_world]
    if len(sizes) != len(obj.data.curves) or any(size < 2 for size in sizes):
        raise ValueError("Native point replacement must preserve curve count and valid sizes.")
    if any(curve.points_length != size for curve, size in zip(obj.data.curves, sizes)):
        obj.data.resize_curves(sizes)
    inverse = obj.matrix_world.inverted()
    flat = [float(value) for points in curves_world for point in points for value in (inverse @ Vector(point))]
    obj.data.attributes["position"].data.foreach_set("vector", flat)
    obj.data.update_tag()


def set_curve_int_attribute(data, name, values):
    values = [int(value) for value in values]
    if len(values) != len(data.curves):
        raise ValueError(f"Attribute '{name}' needs one value per curve.")
    attribute = data.attributes.get(name)
    if attribute and (attribute.data_type != "INT" or attribute.domain != "CURVE"):
        data.attributes.remove(attribute)
        attribute = None
    attribute = attribute or data.attributes.new(name, "INT", "CURVE")
    attribute.data.foreach_set("value", values)
    data.update_tag()


def get_curve_int_attribute(data, name):
    attribute = data.attributes.get(name)
    if not attribute or attribute.data_type != "INT" or attribute.domain != "CURVE":
        return None
    values = [0] * len(attribute.data)
    attribute.data.foreach_get("value", values)
    return values


def set_attachment_surface(obj, scalp, uv_map=""):
    if obj.type != "CURVES" or scalp.type != "MESH":
        raise TypeError("Attachment requires native Hair Curves and a mesh scalp.")
    obj.data.surface = scalp
    obj.data.surface_uv_map = str(uv_map or "")


def asset_library_path():
    return os.path.join(
        bpy.utils.system_resource("DATAFILES"),
        "assets",
        "nodes",
        HAIR_ASSET_FILE,
    )


def load_hair_node_group(asset_name):
    existing = bpy.data.node_groups.get(asset_name)
    if existing:
        return existing
    path = asset_library_path()
    if not os.path.isfile(path):
        raise RuntimeError(f"Blender procedural hair assets not found: {path}")
    with bpy.data.libraries.load(path, link=True, pack=True, set_fake=False) as (source, target):
        if asset_name not in source.node_groups:
            raise ValueError(f"Hair node asset not found: {asset_name}")
        target.node_groups.append(asset_name)
    return target.node_groups[0]


def input_identifiers(node_group):
    result = {}
    for item in node_group.interface.items_tree:
        if getattr(item, "item_type", None) == "SOCKET" and item.in_out == "INPUT":
            result[item.name] = item.identifier
    return result


def set_modifier_input(modifier, socket_name, value):
    identifiers = input_identifiers(modifier.node_group)
    identifier = identifiers.get(socket_name)
    if not identifier:
        for alias in SOCKET_ALIASES.get(socket_name, ()):
            identifier = identifiers.get(alias)
            if identifier:
                break
    if not identifier:
        raise ValueError(f"Node group '{modifier.node_group.name}' has no input '{socket_name}'.")

    modern_inputs = getattr(getattr(modifier, "properties", None), "inputs", None)

    if modern_inputs is not None:
        item = getattr(modern_inputs, identifier, None)
        if item is not None:
            item.value = value

            # Blender 5.x Geometry Nodes modifier-interface values require
            # explicit dependency invalidation before evaluated geometry
            # reliably reflects the new value.
            node_group = modifier.node_group

            try:
                node_group.interface_update(bpy.context)
            except Exception:
                pass

            try:
                node_group.update_tag()
            except Exception:
                pass

            try:
                modifier.id_data.update_tag(refresh={'OBJECT', 'DATA', 'TIME'})
            except Exception:
                pass

            try:
                bpy.context.view_layer.update()
            except Exception:
                pass

            return identifier

    modifier[identifier] = value
    return identifier


def ensure_hair_modifier(obj, modifier_name, asset_name, settings, rebuild=True):
    if obj.type != "CURVES":
        raise TypeError(f"Object '{obj.name}' is not native Hair Curves.")
    existing = obj.modifiers.get(modifier_name)
    if existing and rebuild:
        obj.modifiers.remove(existing)
        existing = None
    modifier = existing or obj.modifiers.new(name=modifier_name, type="NODES")
    modifier.node_group = load_hair_node_group(asset_name)
    applied = {}
    for socket_name, value in settings.items():
        set_modifier_input(modifier, socket_name, value)
        applied[socket_name] = value
    return modifier, applied


def _ensure_resample_flow_node_group():
    """Build a length-aware native Resample Curve graph for deformation detail."""
    existing = bpy.data.node_groups.get(RESAMPLE_FLOW_NODE_GROUP)
    if existing:
        return existing

    group = bpy.data.node_groups.new(RESAMPLE_FLOW_NODE_GROUP, "GeometryNodeTree")
    try:
        interface = group.interface
        interface.new_socket(name="Geometry", in_out='INPUT', socket_type="NodeSocketGeometry")
        interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type="NodeSocketGeometry")
        resolution = interface.new_socket(
            name="Points per Meter", in_out='INPUT', socket_type="NodeSocketFloat"
        )
        resolution.default_value = 24.0
        resolution.min_value = 0.01

        nodes, links = group.nodes, group.links
        group_in = nodes.new("NodeGroupInput")
        group_out = nodes.new("NodeGroupOutput")
        spacing = nodes.new("ShaderNodeMath")
        spacing.operation = 'DIVIDE'
        spacing.inputs[0].default_value = 1.0
        resample = nodes.new("GeometryNodeResampleCurve")
        # Length mode gives every spline approximately the requested sampling
        # density without first reducing all curves to one aggregate length.
        if hasattr(resample, "mode"):
            resample.mode = 'LENGTH'
        elif resample.inputs.get("Mode"):
            resample.inputs["Mode"].default_value = "Length"

        links.new(group_in.outputs["Geometry"], resample.inputs["Curve"])
        links.new(group_in.outputs["Points per Meter"], spacing.inputs[1])
        links.new(spacing.outputs[0], resample.inputs["Length"])
        links.new(resample.outputs["Curve"], group_out.inputs["Geometry"])
        return group
    except Exception:
        bpy.data.node_groups.remove(group)
        raise


def ensure_resample_flow_modifier(obj, modifier_name, points_per_meter, rebuild=True):
    """Reuse one semantic resample modifier; rebuild means update, not duplicate."""
    if obj.type != "CURVES":
        raise TypeError(f"Object '{obj.name}' is not native Hair Curves.")
    matches = [item for item in obj.modifiers if item.name == modifier_name]
    modifier = matches[0] if matches else obj.modifiers.new(name=modifier_name, type="NODES")
    for duplicate in matches[1:]:
        obj.modifiers.remove(duplicate)
    modifier.node_group = _ensure_resample_flow_node_group()
    set_modifier_input(modifier, "Points per Meter", float(points_per_meter))
    flow = obj.modifiers.get("HR Flow Hair Curves")
    if flow and obj.modifiers.find(modifier.name) > obj.modifiers.find(flow.name):
        obj.modifiers.move(obj.modifiers.find(modifier.name), obj.modifiers.find(flow.name))
    return modifier, {"Points per Meter": float(points_per_meter)}


def _map_smootherstep(nodes, links, value, start, end, label, exponent=None):
    node = nodes.new("ShaderNodeMapRange")
    node.label = label
    node.clamp = True
    node.interpolation_type = 'SMOOTHERSTEP'
    node.inputs[1].default_value = float(start)
    node.inputs[2].default_value = float(end)
    node.inputs[3].default_value = 0.0
    node.inputs[4].default_value = 1.0
    links.new(value, node.inputs[0])
    if exponent is None:
        return node.outputs[0]
    power = nodes.new("ShaderNodeMath")
    power.operation = 'POWER'
    power.label = label + " Tension"
    links.new(node.outputs[0], power.inputs[0])
    links.new(exponent, power.inputs[1])
    return power.outputs[0]


def _vector_mix(nodes, links, first, second, factor, label):
    subtract = nodes.new("ShaderNodeVectorMath")
    subtract.operation = 'SUBTRACT'
    subtract.label = label
    links.new(second, subtract.inputs[0])
    links.new(first, subtract.inputs[1])
    scale = nodes.new("ShaderNodeVectorMath")
    scale.operation = 'SCALE'
    links.new(subtract.outputs[0], scale.inputs[0])
    links.new(factor, scale.inputs[3])
    add = nodes.new("ShaderNodeVectorMath")
    add.operation = 'ADD'
    links.new(first, add.inputs[0])
    links.new(scale.outputs[0], add.inputs[1])
    return add.outputs[0]


def _ensure_guide_shaper_node_group():
    """Native normalized-curve shaper; frame vectors are stable object inputs."""
    existing = bpy.data.node_groups.get(GUIDE_SHAPER_NODE_GROUP)
    if existing:
        return existing

    group = bpy.data.node_groups.new(GUIDE_SHAPER_NODE_GROUP, "GeometryNodeTree")
    try:
        interface = group.interface
        interface.new_socket(name="Geometry", in_out='INPUT', socket_type="NodeSocketGeometry")
        interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type="NodeSocketGeometry")
        controls = (
            ("Point Count", "NodeSocketInt", 16),
            ("Root Lock", "NodeSocketFloat", 1.0),
            ("Root Zone", "NodeSocketFloat", 0.12),
            ("Upper Offset", "NodeSocketVector", (0.0, 0.0, 0.0)),
            ("Mid Offset", "NodeSocketVector", (0.0, 0.0, 0.0)),
            ("Lower Offset", "NodeSocketVector", (0.0, 0.0, 0.0)),
            ("Tip Offset", "NodeSocketVector", (0.0, 0.0, 0.0)),
            ("Lift Vector", "NodeSocketVector", (0.0, 0.0, 0.0)),
            ("Lift Zone", "NodeSocketFloat", 0.2),
            ("Fall Vector", "NodeSocketVector", (0.0, 0.0, 0.0)),
            ("Fall Start", "NodeSocketFloat", 0.25),
            ("Tip Direction", "NodeSocketVector", (0.0, 0.0, 0.0)),
            ("Tip Release", "NodeSocketFloat", 0.0),
            ("Tip Zone", "NodeSocketFloat", 0.2),
            ("Envelope Exponent", "NodeSocketFloat", 1.0),
            ("Lift Exponent", "NodeSocketFloat", 1.0),
            ("Fall Exponent", "NodeSocketFloat", 1.0),
            ("Preserve Length", "NodeSocketBool", True),
        )
        for name, socket_type, default in controls:
            socket = interface.new_socket(name=name, in_out='INPUT', socket_type=socket_type)
            socket.default_value = default
            if socket_type == "NodeSocketFloat" and name in {
                "Root Lock", "Root Zone", "Lift Zone", "Fall Start",
                "Tip Release", "Tip Zone",
            }:
                socket.min_value = 0.0
                socket.max_value = 1.0
            elif name.endswith("Exponent"):
                socket.min_value = 0.01
                socket.max_value = 4.0
        nodes, links = group.nodes, group.links
        group_in = nodes.new("NodeGroupInput")
        group_out = nodes.new("NodeGroupOutput")
        resample = nodes.new("GeometryNodeResampleCurve")
        if hasattr(resample, "mode"):
            resample.mode = 'COUNT'
        elif resample.inputs.get("Mode"):
            resample.inputs["Mode"].default_value = "Count"
        spline = nodes.new("GeometryNodeSplineParameter")
        capture = nodes.new("GeometryNodeCaptureAttribute")
        capture.domain = 'POINT'
        capture.capture_items.new('VECTOR', "Reference Position")
        position = nodes.new("GeometryNodeInputPosition")
        set_position = nodes.new("GeometryNodeSetPosition")
        links.new(group_in.outputs["Geometry"], resample.inputs["Curve"])
        links.new(group_in.outputs["Point Count"], resample.inputs["Count"])
        links.new(resample.outputs["Curve"], capture.inputs["Geometry"])
        links.new(position.outputs["Position"], capture.inputs["Reference Position"])

        factor = spline.outputs["Factor"]
        # Semantic envelope anchors: calm root, upper, mid, lower, tip.
        zero = nodes.new("ShaderNodeCombineXYZ").outputs["Vector"]
        u = _map_smootherstep(nodes, links, factor, 0.0, 0.25, "Root to Upper", group_in.outputs["Envelope Exponent"])
        envelope = _vector_mix(nodes, links, zero, group_in.outputs["Upper Offset"], u, "Upper")
        m = _map_smootherstep(nodes, links, factor, 0.25, 0.50, "Upper to Mid", group_in.outputs["Envelope Exponent"])
        envelope = _vector_mix(nodes, links, envelope, group_in.outputs["Mid Offset"], m, "Mid")
        lo = _map_smootherstep(nodes, links, factor, 0.50, 0.75, "Mid to Lower", group_in.outputs["Envelope Exponent"])
        envelope = _vector_mix(nodes, links, envelope, group_in.outputs["Lower Offset"], lo, "Lower")
        ti = _map_smootherstep(nodes, links, factor, 0.75, 1.0, "Lower to Tip", group_in.outputs["Envelope Exponent"])
        envelope = _vector_mix(nodes, links, envelope, group_in.outputs["Tip Offset"], ti, "Tip")

        # Root lock is a smooth multiplier, never a hard semantic segment.
        root_fade = nodes.new("ShaderNodeMapRange")
        root_fade.clamp = True
        root_fade.interpolation_type = 'SMOOTHERSTEP'
        root_fade.inputs[1].default_value = 0.0
        links.new(factor, root_fade.inputs[0])
        links.new(group_in.outputs["Root Zone"], root_fade.inputs[2])
        one_minus_lock = nodes.new("ShaderNodeMath")
        one_minus_lock.operation = 'SUBTRACT'
        one_minus_lock.inputs[0].default_value = 1.0
        links.new(group_in.outputs["Root Lock"], one_minus_lock.inputs[1])
        lock_mix = nodes.new("ShaderNodeMath")
        lock_mix.operation = 'MULTIPLY_ADD'
        links.new(root_fade.outputs[0], lock_mix.inputs[0])
        links.new(group_in.outputs["Root Lock"], lock_mix.inputs[1])
        links.new(one_minus_lock.outputs[0], lock_mix.inputs[2])
        env_scale = nodes.new("ShaderNodeVectorMath")
        env_scale.operation = 'SCALE'
        links.new(envelope, env_scale.inputs[0])
        env_scale.inputs[3].default_value = 1.0

        # Lift is a smooth upper-zone lobe; fall is a progressive gravity ramp.
        lift_out = nodes.new("ShaderNodeMapRange")
        lift_out.clamp = True
        lift_out.interpolation_type = 'SMOOTHERSTEP'
        lift_out.inputs[1].default_value = 0.0
        lift_out.inputs[3].default_value = 1.0
        lift_out.inputs[4].default_value = 0.0
        links.new(factor, lift_out.inputs[0])
        links.new(group_in.outputs["Lift Zone"], lift_out.inputs[2])
        lift_power = nodes.new("ShaderNodeMath")
        lift_power.operation = 'POWER'
        links.new(lift_out.outputs[0], lift_power.inputs[0])
        links.new(group_in.outputs["Lift Exponent"], lift_power.inputs[1])
        lift_scale = nodes.new("ShaderNodeVectorMath")
        lift_scale.operation = 'SCALE'
        links.new(group_in.outputs["Lift Vector"], lift_scale.inputs[0])
        links.new(lift_power.outputs[0], lift_scale.inputs[3])
        fall_ramp = nodes.new("ShaderNodeMapRange")
        fall_ramp.clamp = True
        fall_ramp.interpolation_type = 'SMOOTHERSTEP'
        fall_ramp.inputs[2].default_value = 1.0
        links.new(factor, fall_ramp.inputs[0])
        links.new(group_in.outputs["Fall Start"], fall_ramp.inputs[1])
        fall_power = nodes.new("ShaderNodeMath")
        fall_power.operation = 'POWER'
        links.new(fall_ramp.outputs[0], fall_power.inputs[0])
        links.new(group_in.outputs["Fall Exponent"], fall_power.inputs[1])
        fall_scale = nodes.new("ShaderNodeVectorMath")
        fall_scale.operation = 'SCALE'
        links.new(group_in.outputs["Fall Vector"], fall_scale.inputs[0])
        links.new(fall_power.outputs[0], fall_scale.inputs[3])

        tip_start = nodes.new("ShaderNodeMath")
        tip_start.operation = 'SUBTRACT'
        tip_start.inputs[0].default_value = 1.0
        links.new(group_in.outputs["Tip Zone"], tip_start.inputs[1])
        tip_ramp = nodes.new("ShaderNodeMapRange")
        tip_ramp.clamp = True
        tip_ramp.interpolation_type = 'SMOOTHERSTEP'
        tip_ramp.inputs[2].default_value = 1.0
        links.new(factor, tip_ramp.inputs[0])
        links.new(tip_start.outputs[0], tip_ramp.inputs[1])
        release_factor = nodes.new("ShaderNodeMath")
        release_factor.operation = 'MULTIPLY'
        links.new(tip_ramp.outputs[0], release_factor.inputs[0])
        links.new(group_in.outputs["Tip Release"], release_factor.inputs[1])
        tip_scale = nodes.new("ShaderNodeVectorMath")
        tip_scale.operation = 'SCALE'
        links.new(group_in.outputs["Tip Direction"], tip_scale.inputs[0])
        links.new(release_factor.outputs[0], tip_scale.inputs[3])

        add_lift = nodes.new("ShaderNodeVectorMath"); add_lift.operation = 'ADD'
        add_fall = nodes.new("ShaderNodeVectorMath"); add_fall.operation = 'ADD'
        add_tip = nodes.new("ShaderNodeVectorMath"); add_tip.operation = 'ADD'
        links.new(env_scale.outputs[0], add_lift.inputs[0]); links.new(lift_scale.outputs[0], add_lift.inputs[1])
        links.new(add_lift.outputs[0], add_fall.inputs[0]); links.new(fall_scale.outputs[0], add_fall.inputs[1])
        links.new(add_fall.outputs[0], add_tip.inputs[0]); links.new(tip_scale.outputs[0], add_tip.inputs[1])
        final_scale = nodes.new("ShaderNodeVectorMath")
        final_scale.operation = 'SCALE'
        links.new(add_tip.outputs[0], final_scale.inputs[0])
        links.new(lock_mix.outputs[0], final_scale.inputs[3])
        links.new(capture.outputs["Geometry"], set_position.inputs["Geometry"])
        links.new(final_scale.outputs[0], set_position.inputs["Offset"])

        restore = nodes.new("GeometryNodeGroup")
        restore.node_tree = load_hair_node_group("Restore Curve Segment Length")
        links.new(set_position.outputs["Geometry"], restore.inputs["Curves"])
        links.new(capture.outputs["Reference Position"], restore.inputs["Reference Position"])
        links.new(group_in.outputs["Preserve Length"], restore.inputs["Factor"])
        restore.inputs["Selection"].default_value = True
        restore.inputs["Pin at Parameter"].default_value = 0.0
        links.new(restore.outputs["Curves"], group_out.inputs["Geometry"])
        return group
    except Exception:
        bpy.data.node_groups.remove(group)
        raise


def ensure_guide_shaper_modifier(obj, settings, rebuild=True):
    if obj.type != "CURVES":
        raise TypeError(f"Object '{obj.name}' is not native Hair Curves.")
    name = "HR Guide Shaper"
    matches = [item for item in obj.modifiers if item.name == name]
    modifier = matches[0] if matches else obj.modifiers.new(name=name, type="NODES")
    for duplicate in matches[1:]:
        obj.modifiers.remove(duplicate)
    modifier.node_group = _ensure_guide_shaper_node_group()
    applied = {}
    for socket_name, value in settings.items():
        set_modifier_input(modifier, socket_name, value)
        applied[socket_name] = value
    return modifier, applied


def _flow_math(nodes, operation, first, second=None, name=None):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    if name:
        node.label = name
    if not hasattr(first, "bl_idname"):
        node.inputs[0].default_value = float(first)
    if second is not None and not hasattr(second, "bl_idname"):
        node.inputs[1].default_value = float(second)
    return node


def _ensure_flow_node_group():
    """Build the native field graph used by FLOW; called only by real apply."""
    existing = bpy.data.node_groups.get(FLOW_NODE_GROUP)
    if existing:
        return existing

    group = bpy.data.node_groups.new(FLOW_NODE_GROUP, "GeometryNodeTree")
    try:
        interface = group.interface
        interface.new_socket(name="Geometry", in_out='INPUT', socket_type="NodeSocketGeometry")
        interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type="NodeSocketGeometry")
        controls = (
            ("Factor", "NodeSocketFloat", 0.025),
            ("Root", "NodeSocketFloat", 0.0),
            ("Upper", "NodeSocketFloat", 0.15),
            ("Mid", "NodeSocketFloat", 0.55),
            ("Lower", "NodeSocketFloat", 0.8),
            ("Tip", "NodeSocketFloat", 0.35),
            ("Wavelength", "NodeSocketFloat", 0.75),
            ("Phase", "NodeSocketFloat", 0.0),
            ("Variation", "NodeSocketFloat", 0.08),
            ("Asymmetry", "NodeSocketFloat", 0.08),
            ("Tip Release", "NodeSocketFloat", 0.35),
            ("Seed", "NodeSocketInt", 0),
            ("Preserve Length", "NodeSocketBool", True),
        )
        for name, socket_type, default in controls:
            socket = interface.new_socket(name=name, in_out='INPUT', socket_type=socket_type)
            socket.default_value = default

        nodes, links = group.nodes, group.links
        group_in = nodes.new("NodeGroupInput")
        group_out = nodes.new("NodeGroupOutput")
        set_position = nodes.new("GeometryNodeSetPosition")
        spline = nodes.new("GeometryNodeSplineParameter")
        normal = nodes.new("GeometryNodeInputNormal")
        named_id = nodes.new("GeometryNodeInputNamedAttribute")
        named_id.data_type = 'INT'
        named_id.inputs["Name"].default_value = "guide_curve_index"
        random = nodes.new("FunctionNodeRandomValue")
        random.data_type = 'FLOAT'
        random.inputs["Min"].default_value = -1.0
        random.inputs["Max"].default_value = 1.0
        links.new(named_id.outputs["Attribute"], random.inputs["ID"])
        links.new(group_in.outputs["Seed"], random.inputs["Seed"])

        # Smooth five-control envelope. Each smoothstep activates one quarter
        # of the strand and adds the delta to the preceding control value.
        envelope = group_in.outputs["Root"]
        previous = group_in.outputs["Root"]
        for index, control in enumerate(("Upper", "Mid", "Lower", "Tip")):
            smooth = nodes.new("ShaderNodeMapRange")
            smooth.interpolation_type = 'SMOOTHERSTEP'
            smooth.clamp = True
            smooth.inputs["From Min"].default_value = index * 0.25
            smooth.inputs["From Max"].default_value = (index + 1) * 0.25
            smooth.inputs["To Min"].default_value = 0.0
            smooth.inputs["To Max"].default_value = 1.0
            links.new(spline.outputs["Factor"], smooth.inputs["Value"])
            delta = _flow_math(nodes, 'SUBTRACT', group_in.outputs[control], previous)
            links.new(group_in.outputs[control], delta.inputs[0])
            links.new(previous, delta.inputs[1])
            weighted = _flow_math(nodes, 'MULTIPLY', delta.outputs[0], smooth.outputs["Result"])
            links.new(delta.outputs[0], weighted.inputs[0])
            links.new(smooth.outputs["Result"], weighted.inputs[1])
            add = _flow_math(nodes, 'ADD', envelope, weighted.outputs[0])
            links.new(envelope, add.inputs[0])
            links.new(weighted.outputs[0], add.inputs[1])
            envelope = add.outputs[0]
            previous = group_in.outputs[control]

        safe_wave = _flow_math(nodes, 'MAXIMUM', group_in.outputs["Wavelength"], 0.001)
        links.new(group_in.outputs["Wavelength"], safe_wave.inputs[0])
        angle_scale = _flow_math(nodes, 'DIVIDE', 6.283185307179586, safe_wave.outputs[0])
        links.new(safe_wave.outputs[0], angle_scale.inputs[1])
        angle = _flow_math(nodes, 'MULTIPLY', spline.outputs["Factor"], angle_scale.outputs[0])
        links.new(spline.outputs["Factor"], angle.inputs[0])
        links.new(angle_scale.outputs[0], angle.inputs[1])
        varied = _flow_math(nodes, 'MULTIPLY', random.outputs["Value"], group_in.outputs["Variation"])
        links.new(random.outputs["Value"], varied.inputs[0])
        links.new(group_in.outputs["Variation"], varied.inputs[1])
        phase = _flow_math(nodes, 'ADD', group_in.outputs["Phase"], varied.outputs[0])
        links.new(group_in.outputs["Phase"], phase.inputs[0])
        links.new(varied.outputs[0], phase.inputs[1])
        total_angle = _flow_math(nodes, 'ADD', angle.outputs[0], phase.outputs[0])
        links.new(angle.outputs[0], total_angle.inputs[0])
        links.new(phase.outputs[0], total_angle.inputs[1])
        wave = _flow_math(nodes, 'SINE', total_angle.outputs[0])
        links.new(total_angle.outputs[0], wave.inputs[0])

        squared = _flow_math(nodes, 'MULTIPLY', wave.outputs[0], wave.outputs[0])
        links.new(wave.outputs[0], squared.inputs[0])
        links.new(wave.outputs[0], squared.inputs[1])
        centered = _flow_math(nodes, 'SUBTRACT', squared.outputs[0], 0.5)
        links.new(squared.outputs[0], centered.inputs[0])
        asymmetric = _flow_math(nodes, 'MULTIPLY', centered.outputs[0], group_in.outputs["Asymmetry"])
        links.new(centered.outputs[0], asymmetric.inputs[0])
        links.new(group_in.outputs["Asymmetry"], asymmetric.inputs[1])
        shaped_wave = _flow_math(nodes, 'ADD', wave.outputs[0], asymmetric.outputs[0])
        links.new(wave.outputs[0], shaped_wave.inputs[0])
        links.new(asymmetric.outputs[0], shaped_wave.inputs[1])

        tip_ramp = nodes.new("ShaderNodeMapRange")
        tip_ramp.interpolation_type = 'SMOOTHERSTEP'
        tip_ramp.clamp = True
        tip_ramp.inputs["From Min"].default_value = 0.8
        tip_ramp.inputs["From Max"].default_value = 1.0
        tip_ramp.inputs["To Min"].default_value = 0.0
        tip_ramp.inputs["To Max"].default_value = 1.0
        links.new(spline.outputs["Factor"], tip_ramp.inputs["Value"])
        release_amount = _flow_math(nodes, 'MULTIPLY', tip_ramp.outputs["Result"], group_in.outputs["Tip Release"])
        links.new(tip_ramp.outputs["Result"], release_amount.inputs[0])
        links.new(group_in.outputs["Tip Release"], release_amount.inputs[1])
        release = _flow_math(nodes, 'SUBTRACT', 1.0, release_amount.outputs[0])
        links.new(release_amount.outputs[0], release.inputs[1])

        amplitude = envelope
        for value in (group_in.outputs["Factor"], shaped_wave.outputs[0], release.outputs[0]):
            multiply = _flow_math(nodes, 'MULTIPLY', amplitude, value)
            links.new(amplitude, multiply.inputs[0])
            links.new(value, multiply.inputs[1])
            amplitude = multiply.outputs[0]
        offset = nodes.new("ShaderNodeVectorMath")
        offset.operation = 'SCALE'
        links.new(normal.outputs["Normal"], offset.inputs[0])
        links.new(amplitude, offset.inputs["Scale"])
        links.new(group_in.outputs["Geometry"], set_position.inputs["Geometry"])
        links.new(offset.outputs["Vector"], set_position.inputs["Offset"])
        links.new(set_position.outputs["Geometry"], group_out.inputs["Geometry"])
        return group
    except Exception:
        bpy.data.node_groups.remove(group)
        raise


def ensure_flow_modifier(obj, modifier_name, settings, rebuild=True):
    if obj.type != "CURVES":
        raise TypeError(f"Object '{obj.name}' is not native Hair Curves.")
    existing = obj.modifiers.get(modifier_name)
    if existing and rebuild:
        obj.modifiers.remove(existing)
        existing = None
    modifier = existing or obj.modifiers.new(name=modifier_name, type="NODES")
    modifier.node_group = _ensure_flow_node_group()
    applied = {}
    for socket_name, value in settings.items():
        set_modifier_input(modifier, socket_name, value)
        applied[socket_name] = value
    resample = obj.modifiers.get("HR Resample for Flow")
    if resample:
        flow_index = obj.modifiers.find(modifier.name)
        resample_index = obj.modifiers.find(resample.name)
        if flow_index != resample_index + 1:
            target = resample_index if flow_index < resample_index else resample_index + 1
            obj.modifiers.move(flow_index, target)
    return modifier, applied


def remove_native_object(obj):
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data.users == 0:
        bpy.data.hair_curves.remove(data)
