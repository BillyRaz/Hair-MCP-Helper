"""Hair MCP Helper

A deliberately thin semantic layer for machine-driven hair grooming.
It does not generate hairstyles. It gives Codex/MCP stable names,
structured commands, checkpoints, metadata and validation.
"""

bl_info = {
    "name": "Hair MCP Helper",
    "author": "Bilal Raza + OpenAI Codex workflow",
    "version": (0, 3, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Hair MCP",
    "description": "Semantic bridge for Codex/MCP hair-groom workflows",
    "category": "3D View",
}

from . import core, operators, panel


def register():
    operators.register()
    panel.register()


def unregister():
    panel.unregister()
    operators.unregister()


# Stable machine-facing entry points.
def execute(command):
    """Execute a dict or JSON string command and return a JSON-serializable dict."""
    return core.execute(command)


def snapshot():
    """Return current Hair MCP scene state as a JSON-serializable dict."""
    return core.snapshot_scene()


def validate():
    """Return validation report as a JSON-serializable dict."""
    return core.validate_scene()
