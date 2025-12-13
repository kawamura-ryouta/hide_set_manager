import json
import bpy
from ..utils.logging import log_exc

JSON_VERSION = 1


def export_hide_set(filepath: str, hide_set) -> bool:
    data = {
        "version": JSON_VERSION,
        "name": hide_set.name,
        "mode": hide_set.mode,
        "elements": [
            {
                "object": elem.object_name,
                "type": elem.element_type,
                "pid": elem.index,
                "hidden": bool(elem.saved_hidden),
            }
            for elem in hide_set.elements
        ],
    }

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_exc("export_hide_set", e)
        return False
