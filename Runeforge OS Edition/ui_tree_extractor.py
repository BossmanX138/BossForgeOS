"""
ui_tree_extractor.py

Extracts the Windows UI Automation (UIA) tree for all top-level windows and their controls.
Outputs a structured JSON map of window titles, process names, control hierarchy, roles, names, states, and bounding boxes.

Dependencies:
- uiautomation (pip install uiautomation)
- json

Usage:
    python ui_tree_extractor.py
"""
import uiautomation as auto
import json


def rect_to_dict(rect):
    """Return a stable rectangle payload regardless of UIA rect object shape."""
    if rect is None:
        return None

    # Most UIA Rect objects expose these attributes.
    attrs = ("left", "top", "right", "bottom")
    if all(hasattr(rect, name) for name in attrs):
        try:
            left = int(getattr(rect, "left"))
            top = int(getattr(rect, "top"))
            right = int(getattr(rect, "right"))
            bottom = int(getattr(rect, "bottom"))
            return {
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": max(0, right - left),
                "height": max(0, bottom - top),
            }
        except Exception:
            pass

    # Fallback for iterable rectangle-like values.
    try:
        parts = list(rect)
        if len(parts) >= 4:
            left = int(parts[0])
            top = int(parts[1])
            right = int(parts[2])
            bottom = int(parts[3])
            return {
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": max(0, right - left),
                "height": max(0, bottom - top),
            }
    except Exception:
        pass

    return None

def get_control_info(control):
    info = {
        'name': control.Name,
        'automation_id': control.AutomationId,
        'control_type': control.ControlTypeName,
        'class_name': control.ClassName,
        'rect': rect_to_dict(control.BoundingRectangle),
        'enabled': control.IsEnabled,
        'visible': control.IsOffscreen is False,
        'children': []
    }
    # Limit depth for performance
    try:
        for child in control.GetChildren():
            info['children'].append(get_control_info(child))
    except Exception:
        pass
    return info

def get_ui_tree():
    windows = []
    for window in auto.GetRootControl().GetChildren():
        if window.ControlTypeName == 'WindowControl':
            win_info = {
                'title': window.Name,
                'process_id': window.ProcessId,
                'class_name': window.ClassName,
                'rect': rect_to_dict(window.BoundingRectangle),
                'enabled': window.IsEnabled,
                'visible': window.IsOffscreen is False,
                'controls': []
            }
            try:
                for child in window.GetChildren():
                    win_info['controls'].append(get_control_info(child))
            except Exception:
                pass
            windows.append(win_info)
    return {'windows': windows}

def main():
    tree = get_ui_tree()
    # Keep output terminal-safe on cp1252 consoles.
    print(json.dumps(tree, indent=2, ensure_ascii=True))

if __name__ == '__main__':
    main()
