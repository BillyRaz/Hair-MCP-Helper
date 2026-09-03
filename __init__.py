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

from . import core, operators, panel, styler


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


def style_capabilities():
    return styler.capabilities()


def plan_style(profile="RAZ_ARII_HAIR_V1", regions=None, rebuild=True):
    return styler.plan_style(profile, regions=regions, rebuild=rebuild)


def apply_style(profile="RAZ_ARII_HAIR_V1", regions=None, rebuild=True):
    return styler.apply_style(profile, regions=regions, rebuild=rebuild)


def configure_flow(*args, **kwargs):
    return core.configure_flow(*args, **kwargs)


def configure_resample_flow(*args, **kwargs):
    return core.configure_resample_flow(*args, **kwargs)
