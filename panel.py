import bpy


class HAIRMCP_PT_main(bpy.types.Panel):
    bl_label = "Hair MCP Helper"
    bl_idname = "HAIRMCP_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Hair MCP"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        col.operator("hairmcp.init", icon="OUTLINER_COLLECTION")
        col.operator("hairmcp.set_scalp", icon="MESH_DATA")

        layout.separator()
        layout.label(text=f"Scalp: {scene.get('hair_mcp_scalp', 'NOT SET')}")
        layout.label(text=f"Checkpoint: {scene.get('hair_mcp_checkpoint', 'NONE')}")

        layout.separator()
        col = layout.column(align=True)
        col.operator("hairmcp.tag_selected", icon="TAG")
        col.operator("hairmcp.checkpoint", icon="BOOKMARKS")

        layout.separator()
        col = layout.column(align=True)
        col.operator("hairmcp.validate", icon="CHECKMARK")
        col.operator("hairmcp.snapshot", icon="TEXT")

        box = layout.box()
        box.label(text="Machine API")
        box.label(text="import hair_mcp_helper as hmh")
        box.label(text="hmh.execute({...})")


classes = (HAIRMCP_PT_main,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
