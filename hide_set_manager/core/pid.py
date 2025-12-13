from typing import Any, Dict, Tuple

import bmesh
import bpy

from ..utils.logging import log_exc


def assign_persistent_id_if_missing(
    bm: bmesh.types.BMesh,
    v_layer,
    e_layer,
    f_layer,
    elem,
    etype: str,
    scene,
) -> int:
    """要素に永続IDがなければ新しく振って、そのIDを返す。"""

    try:
        next_id = int(scene.hm_next_elem_id)
        if next_id < 1:
            next_id = 1
    except Exception:
        next_id = 1

    if etype == "VERT":
        layer = v_layer
    elif etype == "EDGE":
        layer = e_layer
    else:
        layer = f_layer

    if layer is None:
        return int(getattr(elem, "index", -1))

    try:
         pid = int(elem[layer])
    except Exception:
        pid = 0

    # 0や負値 → PIDなしなので新規付与
    if pid <= 0:
        new_pid = int(scene.hm_next_elem_id)
        elem[layer] = new_pid
        scene.hm_next_elem_id = new_pid + 1
        return new_pid

    return pid

    # 新規IDを割り振る
    new_pid = next_id
    try:
        elem[layer] = new_pid
        scene.hm_next_elem_id = new_pid + 1
    except Exception as e:
        log_exc("assign_persistent_id_if_missing", e)

    return new_pid


def ensure_id_layers(bm: bmesh.types.BMesh) -> Tuple[Any, Any, Any]:
    """頂点/辺/面用の永続IDレイヤーを取得（なければ作成）。"""

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


def build_pid_maps(bm: bmesh.types.BMesh):
    """
    PID → 実際の頂点/辺/面を引けるように辞書を作る。
    すでにPIDが入っていることを前提とする。
    """

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

    def fill(layer, elems, out_dict):
        if layer is None:
            return
        for elem in elems:
            try:
                pid = int(elem[layer])
            except Exception:
                continue
            if pid > 0:
                out_dict[pid] = elem

    fill(v_layer, bm.verts, v_map)
    fill(e_layer, bm.edges, e_map)
    fill(f_layer, bm.faces, f_map)

    return v_map, e_map, f_map, v_layer, e_layer, f_layer
