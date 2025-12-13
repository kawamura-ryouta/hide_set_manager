import bpy
import bmesh
from typing import Any, Dict, List, Tuple

from .utils_logging import log_exc
from .utils_safe_hidden import safe_set_hidden


# -------------------------------------------------------
# 永続IDレイヤーを取得（なければ作成）
# -------------------------------------------------------
def ensure_id_layers(bm: bmesh.types.BMesh) -> Tuple[Any, Any, Any]:
    """
    頂点/辺/面用の永続IDレイヤーを取得（なければ作成）。
    """
    def _ensure(layer_group, name: str):
        layer = layer_group.get(name)
        if layer is None:
            layer = layer_group.new(name)
        return layer

    try:
        v_layer = _ensure(bm.verts.layers.int, "hm_vid")
        e_layer = _ensure(bm.edges.layers.int, "hm_eid")
        f_layer = _ensure(bm.faces.layers.int, "hm_fid")
    except Exception as e:
        log_exc("ensure_id_layers", e)
        return None, None, None

    return v_layer, e_layer, f_layer


# -------------------------------------------------------
# PID → 実際の頂点/辺/面 に変換できる辞書を構築
# -------------------------------------------------------
def build_pid_maps(bm: bmesh.types.BMesh):
    def _get(layer_group, name: str):
        try:
            return layer_group.get(name)
        except Exception as e:
            log_exc(f"build_pid_maps.get.{name}", e)
            return None

    v_layer = _get(bm.verts.layers.int, "hm_vid")
    e_layer = _get(bm.edges.layers.int, "hm_eid")
    f_layer = _get(bm.faces.layers.int, "hm_fid")

    v_map: Dict[int, Any] = {}
    e_map: Dict[int, Any] = {}
    f_map: Dict[int, Any] = {}

    def fill(layer, elems, dst):
        if layer is None:
            return
        for elem in elems:
            try:
                pid = int(elem[layer])
            except Exception:
                continue
            if pid > 0:
                dst[pid] = elem

    fill(v_layer, bm.verts, v_map)
    fill(e_layer, bm.edges, e_map)
    fill(f_layer, bm.faces, f_map)

    return v_map, e_map, f_map, v_layer, e_layer, f_layer


# -------------------------------------------------------
# PIDを基に表示/非表示を適用
# -------------------------------------------------------
def hide_elements_with_rules_on_bmesh_by_pid(
    bm: bmesh.types.BMesh,
    pid_items: List[Any],
    hide_flag: bool,
    v_map: Dict[int, Any],
    e_map: Dict[int, Any],
    f_map: Dict[int, Any],
) -> None:

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

    # 辺 + 接続面
    for e in edges:
        safe_set_hidden(e, hide_flag)
        for lf in getattr(e, "link_faces", []):
            safe_set_hidden(lf, hide_flag)

    # 頂点 + 接続面
    for v in verts:
        safe_set_hidden(v, hide_flag)
        for lf in getattr(v, "link_faces", []):
            safe_set_hidden(lf, hide_flag)


# -------------------------------------------------------
# BMesh 処理用ラッパ
# -------------------------------------------------------
def process_bmesh(obj: bpy.types.Object, edit_objs, callback):
    """
    bmesh を使った処理をまとめて行う。
    - 編集モード中なら from_edit_mesh()
    - その他は new() → from_mesh()
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
