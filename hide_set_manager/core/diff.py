"""
差分同期機能用モジュール。

・現在のシーン状態（非表示 / 表示）と
・保存されている HM_HideSet.saved_hidden

を突き合わせて、

- saved_hidden を「今の状態」に更新
- 対応する要素/オブジェクトが消えていたらセットから削除

を行います。

※要素の「追加」は、まずは安全のため行わず、
  既存メンバーの状態同期＋消えた要素のクリーンアップに限定しています。
"""

from dataclasses import dataclass
from typing import Dict, List, Set
import bpy
import bmesh

from .registry import (
    HM_HideSet,
    HM_ElementRef,
    split_items_by_object,
    ensure_objects_in_edit_mode,
)
from .pid import build_pid_maps
from ..utils.safe_hidden import safe_get_hidden
from ..utils.logging import log_exc


@dataclass
class HideSetDiffResult:
    added: int = 0
    removed: int = 0
    updated: int = 0

    @property
    def has_changes(self) -> bool:
        return (self.added + self.removed + self.updated) > 0


def sync_hide_set_saved_hidden(context, hide_set: HM_HideSet) -> HideSetDiffResult:
    if hide_set.mode == "OBJECT":
        return _sync_object_mode(context, hide_set)
    else:
        return _sync_edit_mode(context, hide_set)


# ----------------------------------------------------------------------
# OBJECT モード用
# ----------------------------------------------------------------------
def _sync_object_mode(context, hide_set: HM_HideSet) -> HideSetDiffResult:
    result = HideSetDiffResult()
    scene = context.scene

    to_remove: List[int] = []

    for idx, ref in list(enumerate(hide_set.elements)):
        obj = scene.objects.get(ref.object_name)
        if obj is None:
            to_remove.append(idx)
            result.removed += 1
            continue

        try:
            current_hidden = bool(safe_get_hidden(obj))
        except Exception as e:
            log_exc("_sync_object_mode.safe_get_hidden", e)
            continue

        if current_hidden != bool(ref.saved_hidden):
            ref.saved_hidden = current_hidden
            result.updated += 1

    for idx in sorted(to_remove, reverse=True):
        try:
            hide_set.elements.remove(idx)
        except Exception as e:
            log_exc("_sync_object_mode.remove", e)

    return result


# ----------------------------------------------------------------------
# EDIT（頂点 / 辺 / 面）用
# ----------------------------------------------------------------------
def _sync_edit_mode(context, hide_set: HM_HideSet) -> HideSetDiffResult:
    result = HideSetDiffResult()
    scene = context.scene

    items_by_object = split_items_by_object(hide_set)
    edit_objs = set(ensure_objects_in_edit_mode(context))

    for obj_name, items in items_by_object.items():
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            for _ in items:
                result.removed += 1
            return result

        def _sync_bm(bm: bmesh.types.BMesh):
            v_map, e_map, f_map, *_ = build_pid_maps(bm)

            for ref in items:
                pid = int(ref.index)
                if hide_set.mode == "VERT":
                    elem = v_map.get(pid)
                elif hide_set.mode == "EDGE":
                    elem = e_map.get(pid)
                else:
                    elem = f_map.get(pid)

                if elem is None:
                    result.removed += 1
                    continue

                current_hidden = bool(elem.hide)
                if current_hidden != bool(ref.saved_hidden):
                    ref.saved_hidden = current_hidden
                    result.updated += 1

        try:
            from .bmesh_ops import process_bmesh
            process_bmesh(obj, edit_objs, _sync_bm)
        except Exception as e:
            log_exc("_sync_edit_mode.process_bmesh", e)

    return result


# UI用差分チェック（データ変更なし：完全読み取り専用）
def preview_hide_set_diff(context, hide_set: HM_HideSet) -> HideSetDiffResult:
    result = HideSetDiffResult()

    # オブジェクトモード差分
    if hide_set.mode == "OBJECT":
        scene = context.scene
        for ref in hide_set.elements:
            obj = scene.objects.get(ref.object_name) or bpy.data.objects.get(ref.object_name)
            if obj is None:
                # オブジェクト自体が消えていたら削除と見なす
                result.removed += 1
                continue

            try:
                current_hidden = bool(safe_get_hidden(obj))
            except Exception:
                continue

            # saved_hidden と現在の非表示状態を比較
            if current_hidden != bool(ref.saved_hidden):
                result.updated += 1

        return result


    # 編集モード（頂点 / 辺 / 面）の差分
    items_by_object = split_items_by_object(hide_set)
    if not items_by_object:
        return result

    edit_objs = set(ensure_objects_in_edit_mode(context))

    for obj_name, items in items_by_object.items():
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            # オブジェクト自体が消えている
            result.removed += len(items)
            continue

        def _check(bm: bmesh.types.BMesh):
            nonlocal result
            try:
                v_map, e_map, f_map, *_ = build_pid_maps(bm)
            except Exception as e:
                log_exc("preview_hide_set_diff.edit.build_pid_maps", e)
                return

            for ref in items:
                try:
                    pid = int(ref.index)
                except Exception:
                    continue

                if hide_set.mode == "VERT":
                    elem = v_map.get(pid)
                elif hide_set.mode == "EDGE":
                    elem = e_map.get(pid)
                else:  # "FACE"
                    elem = f_map.get(pid)

                if elem is None:
                    # 要素自体が見つからない → 拓扑的に消えた
                    result.removed += 1
                    continue

                try:
                    current_hidden = bool(getattr(elem, "hide", False))
                except Exception:
                    continue

                if current_hidden != bool(ref.saved_hidden):
                    result.updated += 1

        try:
            from .bmesh_ops import process_bmesh
            process_bmesh(obj, edit_objs, _check)
        except Exception as e:
            log_exc("preview_hide_set_diff.edit.process_bmesh", e)

    return result
