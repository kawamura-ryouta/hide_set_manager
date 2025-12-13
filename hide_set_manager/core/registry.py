from typing import Dict, List

import bpy

from ..utils.safe_hidden import safe_get_hidden
from ..utils.logging import log_exc
from .bmesh_ops import process_bmesh
from .pid import build_pid_maps


class HM_ElementRef(bpy.types.PropertyGroup):
    """1つの要素（またはオブジェクト）への参照情報"""

    object_name: bpy.props.StringProperty(default="")
    element_type: bpy.props.EnumProperty(
        items=[
            ("VERT", "頂点", ""),
            ("EDGE", "辺", ""),
            ("FACE", "面", ""),
            ("OBJECT", "オブジェクト", ""),
        ],
        default="VERT",
    )
    # 永続ID
    index: bpy.props.IntProperty(default=-1)
    # 登録時点での非表示状態（あとで復元用）
    saved_hidden: bpy.props.BoolProperty(default=False)


class HM_HideSet(bpy.types.PropertyGroup):
    """非表示セット1つ分"""

    name: bpy.props.StringProperty(default="Untitled")
    mode: bpy.props.EnumProperty(
        items=[
            ("VERT", "頂点", ""),
            ("EDGE", "辺", ""),
            ("FACE", "面", ""),
            ("OBJECT", "オブジェクト", ""),
        ],
        default="VERT",
    )
    elements: bpy.props.CollectionProperty(type=HM_ElementRef)


def split_items_by_object(hide_set: HM_HideSet) -> Dict[str, List[HM_ElementRef]]:
    """同じオブジェクトごとに要素をまとめる。"""
    result: Dict[str, List[HM_ElementRef]] = {}
    for it in hide_set.elements:
        result.setdefault(it.object_name, []).append(it)
    return result


def ensure_objects_in_edit_mode(context) -> List[bpy.types.Object]:
    """
    編集モード対象のオブジェクト一覧を返す。
    Blender 4.x では context.objects_in_mode があるので、それを優先。
    """
    objs = getattr(context, "objects_in_mode", None)
    if objs:
        return list(objs)
    return list(context.selected_objects)


def add_item_unique(collection, obj_name: str, elem_type: str, pid: int, saved_hidden: bool) -> bool:
    """同じ (オブジェクト, タイプ, ID) があれば追加しない。"""
    key = (obj_name, elem_type, int(pid))
    for it in collection:
        if (it.object_name, it.element_type, it.index) == key:
            return False

    new_item: HM_ElementRef = collection.add()
    new_item.object_name = obj_name
    new_item.element_type = elem_type
    new_item.index = int(pid)
    new_item.saved_hidden = bool(saved_hidden)
    return True


def get_mode_label(mode: str) -> str:
    mapping = {
        "VERT": "頂点",
        "EDGE": "辺",
        "FACE": "面",
        "OBJECT": "オブジェクト",
    }
    return mapping.get(mode, mode)


def hide_set_is_completely_hidden(hide_set: HM_HideSet, context) -> bool:
    """非表示セット内の要素が全て非表示なら True。"""

    # オブジェクトモード
    if hide_set.mode == "OBJECT":
        any_obj = False
        for it in hide_set.elements:
            obj = bpy.data.objects.get(it.object_name)
            if not obj:
                continue
            any_obj = True
            # ↑ インデントミスがあればここ調整してください
            if not safe_get_hidden(obj):
                return False
        return any_obj

    # 編集モード（メッシュ要素）
    d = split_items_by_object(hide_set)
    if not d:
        return False

    edit_objs = set(ensure_objects_in_edit_mode(context))
    all_hidden = True

    for obj_name, items in d.items():
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue

        def _check(bm):
            nonlocal all_hidden
            try:
                v_map, e_map, f_map, *_ = build_pid_maps(bm)
            except Exception as e:
                log_exc("hide_set_is_completely_hidden.build_pid_maps", e)
                all_hidden = False
                return

            for it in items:
                try:
                    pid = int(it.index)
                except Exception:
                    continue

                elem = None
                if it.element_type == "VERT":
                    elem = v_map.get(pid)
                elif it.element_type == "EDGE":
                    elem = e_map.get(pid)
                elif it.element_type == "FACE":
                    elem = f_map.get(pid)

                if elem and not getattr(elem, "hide", False):
                    all_hidden = False
                    break

        process_bmesh(obj, edit_objs, _check)
        if not all_hidden:
            break

    return all_hidden
