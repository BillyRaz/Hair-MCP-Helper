import json
import bpy
from bpy.props import EnumProperty, StringProperty, FloatProperty

from . import core


class HAIRMCP_OT_init(bpy.types.Operator):
    bl_idname = "hairmcp.init"
    bl_label = "Initialize Hair MCP"
    bl_description = "Create the semantic Hair MCP collection structure"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        core.ensure_structure()
        core.write_machine_state()
        self.report({"INFO"}, "Hair MCP structure initialized")
        return {"FINISHED"}


class HAIRMCP_OT_set_scalp(bpy.types.Operator):
    bl_idname = "hairmcp.set_scalp"
    bl_label = "Tag Active as Scalp"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        result = core.set_scalp()
        self.report({"INFO"}, f"Scalp: {result['scalp']}")
        return {"FINISHED"}


class HAIRMCP_OT_tag_selected(bpy.types.Operator):
    bl_idname = "hairmcp.tag_selected"
    bl_label = "Tag Selected"
    bl_options = {"REGISTER", "UNDO"}

    role: EnumProperty(
        name="Role",
        items=[(r, r.replace("_", " ").title(), "") for r in sorted(core.ROLE_VALUES)],
        default="GUIDE",
    )
    region: StringProperty(name="Region", default="UNASSIGNED")

    def execute(self, context):
        core.tag_selected(self.role, self.region)
        self.report({"INFO"}, f"Tagged selected as {self.role}")
        return {"FINISHED"}


class HAIRMCP_OT_checkpoint(bpy.types.Operator):
    bl_idname = "hairmcp.checkpoint"
    bl_label = "Save Checkpoint"
    bl_options = {"REGISTER"}

    checkpoint: EnumProperty(
        name="Checkpoint",
        items=[(x, x.replace("_", " ").title(), "") for x in core.CHECKPOINT_ORDER],
        default="A_SCALP_REGIONS",
    )
    note: StringProperty(name="Note", default="")

    def execute(self, context):
        core.checkpoint(self.checkpoint, self.note)
        self.report({"INFO"}, f"Checkpoint {self.checkpoint}")
        return {"FINISHED"}


class HAIRMCP_OT_validate(bpy.types.Operator):
    bl_idname = "hairmcp.validate"
    bl_label = "Validate Hair Scene"

    root_tolerance: FloatProperty(name="Root Tolerance", default=0.01, min=0.0, precision=4)

    def execute(self, context):
        report = core.validate_scene(root_tolerance=self.root_tolerance)
        text = bpy.data.texts.get("HR_VALIDATION.json") or bpy.data.texts.new("HR_VALIDATION.json")
        text.clear()
        text.write(json.dumps(report, indent=2))
        if report["ok"]:
            self.report({"INFO"}, f"Validation passed ({len(report['warnings'])} warnings)")
        else:
            self.report({"WARNING"}, f"Validation found {len(report['issues'])} issues")
        return {"FINISHED"}


class HAIRMCP_OT_snapshot(bpy.types.Operator):
    bl_idname = "hairmcp.snapshot"
    bl_label = "Write Machine State"

    def execute(self, context):
        core.write_machine_state()
        self.report({"INFO"}, "Updated HR_MACHINE_STATE.json")
        return {"FINISHED"}


classes = (
    HAIRMCP_OT_init,
    HAIRMCP_OT_set_scalp,
    HAIRMCP_OT_tag_selected,
    HAIRMCP_OT_checkpoint,
    HAIRMCP_OT_validate,
    HAIRMCP_OT_snapshot,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
