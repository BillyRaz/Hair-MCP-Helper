"""Version-sensitive Blender Hair Curves and node-asset helpers."""

import os

import bpy
from mathutils import Vector


HAIR_ASSET_FILE = "procedural_hair_node_assets.blend"
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


def remove_native_object(obj):
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data.users == 0:
        bpy.data.hair_curves.remove(data)

