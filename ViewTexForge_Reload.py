"""
ViewTexForge - Development Reload Script
========================================

Run this script from Blender's Text Editor while developing ViewTexForge.
It unregisters the currently loaded add-on, removes ViewTexForge modules
from sys.modules, invalidates import caches, imports the add-on again,
and registers the fresh code.

This is intended for development only.
"""

import sys
import importlib
import traceback

import bpy


ADDON_DISPLAY_NAME = "ViewTexForge"
ADDON_PACKAGE_BASENAME = "view_tex_forge"


def _find_loaded_root_module_name():
    """Find the actual imported root package name.

    Supports both classic add-on imports:
        view_tex_forge

    and Blender extension-style namespaces such as:
        bl_ext.user_default.view_tex_forge
    """
    candidates = []

    for name, module in list(sys.modules.items()):
        if module is None:
            continue

        if name == ADDON_PACKAGE_BASENAME or name.endswith("." + ADDON_PACKAGE_BASENAME):
            candidates.append(name)
            continue

        bl_info = getattr(module, "bl_info", None)
        if isinstance(bl_info, dict) and bl_info.get("name") == ADDON_DISPLAY_NAME:
            candidates.append(name)

    if not candidates:
        return None

    # Prefer the shortest matching root package rather than one of its children.
    candidates = sorted(set(candidates), key=lambda n: (n.count("."), len(n)))

    for candidate in candidates:
        # A root package normally has a package path.
        module = sys.modules.get(candidate)
        if module is not None and hasattr(module, "__path__"):
            return candidate

    return candidates[0]


def _find_addon_module_via_addon_utils():
    """Try to locate an installed ViewTexForge add-on if it is not loaded."""
    try:
        import addon_utils
        modules = addon_utils.modules(refresh=True)
    except Exception:
        return None

    for module in modules:
        bl_info = getattr(module, "bl_info", None)
        module_name = getattr(module, "__name__", "")

        if isinstance(bl_info, dict) and bl_info.get("name") == ADDON_DISPLAY_NAME:
            return module_name

        if module_name == ADDON_PACKAGE_BASENAME or module_name.endswith("." + ADDON_PACKAGE_BASENAME):
            return module_name

    return None


def _unregister_old_addon(root_module_name):
    module = sys.modules.get(root_module_name)
    if module is None:
        return

    unregister = getattr(module, "unregister", None)
    if not callable(unregister):
        return

    print("[ViewTexForge Reload] Unregistering old add-on...")

    try:
        unregister()
    except Exception as exc:
        # During development, registration state may already be partially broken.
        # Continue with module cleanup so a fresh import still has a chance to work.
        print("[ViewTexForge Reload] Warning: unregister() raised an exception:")
        print("  {}".format(exc))
        traceback.print_exc()


def _remove_modules(root_module_name):
    """Remove the root package and every child module from sys.modules."""
    prefix = root_module_name + "."

    names = [
        name for name in list(sys.modules.keys())
        if name == root_module_name or name.startswith(prefix)
    ]

    # Remove child modules first, root package last.
    names.sort(key=lambda n: n.count("."), reverse=True)

    print("[ViewTexForge Reload] Removing {} cached module(s)...".format(len(names)))
    for name in names:
        print("  - {}".format(name))
        sys.modules.pop(name, None)


def _import_fresh_addon(root_module_name):
    importlib.invalidate_caches()

    print("[ViewTexForge Reload] Importing fresh add-on: {}".format(root_module_name))
    module = importlib.import_module(root_module_name)

    register = getattr(module, "register", None)
    if not callable(register):
        raise RuntimeError(
            "Freshly imported module '{}' has no callable register().".format(root_module_name)
        )

    print("[ViewTexForge Reload] Registering fresh add-on...")
    register()
    return module


def reload_view_tex_forge():
    print("\n" + "=" * 72)
    print("ViewTexForge development reload")
    print("=" * 72)

    root_module_name = _find_loaded_root_module_name()

    if root_module_name is None:
        root_module_name = _find_addon_module_via_addon_utils()

    if root_module_name is None:
        # Classic installation fallback.
        root_module_name = ADDON_PACKAGE_BASENAME

    print("[ViewTexForge Reload] Root module: {}".format(root_module_name))

    _unregister_old_addon(root_module_name)
    _remove_modules(root_module_name)

    try:
        fresh_module = _import_fresh_addon(root_module_name)
    except Exception:
        print("[ViewTexForge Reload] FAILED")
        traceback.print_exc()
        raise

    bl_info = getattr(fresh_module, "bl_info", {}) or {}
    version = bl_info.get("version")
    version_text = ".".join(str(v) for v in version) if version else "unknown"
    module_file = getattr(fresh_module, "__file__", "unknown")

    print("[ViewTexForge Reload] SUCCESS")
    print("[ViewTexForge Reload] Version : {}".format(version_text))
    print("[ViewTexForge Reload] File    : {}".format(module_file))
    print("=" * 72 + "\n")

    # Redraw Blender UI so the refreshed panel appears immediately.
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception:
        pass

    return fresh_module


if __name__ == "__main__":
    reload_view_tex_forge()
