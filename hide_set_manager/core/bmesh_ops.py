from typing import Any, Dict, List

import bmesh
import bpy

from ..utils.safe_hidden import safe_set_hidden
from ..utils.logging import log_exc


def hide_elements_with_rules_on_bmesh_by_pid(
    bm: bmesh.types.BMesh,
    pid_items,
    hide_flag: bool,
    v_map: Dict[int, Any],
    e_map: Dict[int, Any],
    f_map: Dict[int, Any],
) -> None:
    """
    PIDから実際の要素を引いて、非表示/表示を適用する。
    辺や頂点の場合は接続面も一緒に処理する。
    """
    verts: List[Any] = []
    edges: List[Any] = []
    faces: List[Any] = []

    for it in pid_items:
        try:
            pid = int(it.index)
        except Exception:
            continue

        if it.element_type == "VERT":
            v = v_map.get(pid)
            if v is not None:
                verts.append(v)
        elif it.element_type == "EDGE":
            e = e_map.get(pid)
            if e is not None:
                edges.append(e)
        elif it.element_type == "FACE":
            f = f_map.get(pid)
            if f is not None:
                faces.append(f)

    # 面
    for f in faces:
        safe_set_hidden(f, hide_flag)

    # 辺＋接続面
    for e in edges:
        safe_set_hidden(e, hide_flag)
        for lf in getattr(e, "link_faces", []):
            safe_set_hidden(lf, hide_flag)

    # 頂点＋接続面
    for v in verts:
        safe_set_hidden(v, hide_flag)
        for lf in getattr(v, "link_faces", []):
            safe_set_hidden(lf, hide_flag)


def process_bmesh(obj: bpy.types.Object, edit_objs, callback):
    """
    bmesh を使った処理をまとめて行う。
    - 編集モード中のオブジェクトなら from_edit_mesh
    - それ以外は new() → from_mesh
    callback(bm) の中で実際の処理を行う。
    """
    me = obj.data
    is_edit = obj in edit_objs

    if is_edit:
        bm = bmesh.from_edit_mesh(me)
    else:
        bm = bmesh.new()
        bm.from_mesh(me)

    try:
        callback(bm)
        if is_edit:
            bmesh.update_edit_mesh(me)
        else:
            bm.to_mesh(me)
            me.update()
    except Exception as e:
        log_exc("process_bmesh.callback", e)
    finally:
        if not is_edit:
            try:
                bm.free()
            except Exception as e:
                log_exc("process_bmesh.free", e)
