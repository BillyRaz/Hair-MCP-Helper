"""Resolve Hair MCP Helper without depending on Blender's install namespace."""

import importlib
import sys


EXTENSION_ID = "hair_mcp_helper"
ADDON_NAME = "Hair MCP Helper"


def _is_hair_mcp_module(module):
    if module is None or not callable(getattr(module, "execute", None)):
        return False
    info = getattr(module, "bl_info", {}) or {}
    module_name = getattr(module, "__name__", "")
    return (
        info.get("name") == ADDON_NAME
        or module_name == EXTENSION_ID
        or module_name.endswith("." + EXTENSION_ID)
    )


def resolve_hair_mcp_helper():
    """Return the enabled extension module across legacy and bl_ext installs."""
    for module in tuple(sys.modules.values()):
        if _is_hair_mcp_module(module):
            return module

    try:
        import addon_utils

        for module in addon_utils.modules(refresh=False):
            if _is_hair_mcp_module(module):
                return importlib.import_module(module.__name__)
    except (ImportError, AttributeError, RuntimeError):
        pass

    try:
        module = importlib.import_module(EXTENSION_ID)
    except ImportError as exc:
        raise ImportError(
            "Hair MCP Helper is not enabled or could not be resolved. "
            "Enable the extension whose manifest id is 'hair_mcp_helper'."
        ) from exc
    if not _is_hair_mcp_module(module):
        raise ImportError("Resolved module does not expose the Hair MCP semantic API.")
    return module

