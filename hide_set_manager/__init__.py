bl_info = {
    "name": "非表示セットマネージャー  Hide Set Manager (Object Mode, Edit Mode)",
    "author": "kawamura",
    "version": (3, 3, 0),
    "blender": (5, 0, 0),
    "location": "3Dビューポート > サイドバー > 非表示管理",
    "description": "非表示セットとして登録した要素と、その直接接続された要素を非表示にし、トグルや復元を行う Hide Manager（永続IDベース）。",
    "warning": "アドオンはテスト中です",
    "support": "TESTING",
    "category": "Object",
}

import bpy

from .utils.logging import log_exc
from .core.registry import HM_ElementRef, HM_HideSet
from .ui.operators import (
    HM_ApplyHideSet,     # 非表示を適用
    HM_RegisterHideSet,  # 新しく登録
    HM_ToggleHideSet,
    HM_RenameHideSet,
    HM_DeleteHideSet,
    HM_SyncHideSet,
    HM_ExportHideSet,
)
from .ui.panels import HM_PT_EditHideSets, HM_PT_ObjectHideSets


classes = (
    HM_ElementRef,
    HM_HideSet,
    HM_ApplyHideSet,
    HM_RegisterHideSet,
    HM_ToggleHideSet,
    HM_RenameHideSet,
    HM_DeleteHideSet,
    HM_SyncHideSet,
    HM_ExportHideSet,
    HM_PT_EditHideSets,
    HM_PT_ObjectHideSets,
)


def register():
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except Exception as e:
            log_exc(f"register class {c}", e)

    # Sceneプロパティ
    try:
        if not hasattr(bpy.types.Scene, "hm_edit_sets"):
            bpy.types.Scene.hm_edit_sets = bpy.props.CollectionProperty(type=HM_HideSet)
    except Exception as e:
        log_exc("register.hm_edit_sets", e)

    try:
        if not hasattr(bpy.types.Scene, "hm_object_sets"):
            bpy.types.Scene.hm_object_sets = bpy.props.CollectionProperty(type=HM_HideSet)
    except Exception as e:
        log_exc("register.hm_object_sets", e)

    try:
        if not hasattr(bpy.types.Scene, "hm_next_elem_id"):
            bpy.types.Scene.hm_next_elem_id = bpy.props.IntProperty(
                name="次の永続ID",
                default=1,
            )
    except Exception as e:
        log_exc("register.hm_next_elem_id", e)


def unregister():
    # Sceneプロパティ削除
    try:
        if hasattr(bpy.types.Scene, "hm_edit_sets"):
            del bpy.types.Scene.hm_edit_sets
    except Exception as e:
        log_exc("unregister.hm_edit_sets", e)

    try:
        if hasattr(bpy.types.Scene, "hm_object_sets"):
            del bpy.types.Scene.hm_object_sets
    except Exception as e:
        log_exc("unregister.hm_object_sets", e)

    try:
        if hasattr(bpy.types.Scene, "hm_next_elem_id"):
            del bpy.types.Scene.hm_next_elem_id
    except Exception as e:
        log_exc("unregister.hm_next_elem_id", e)

    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception as e:
            log_exc(f"unregister class {c}", e)


if __name__ == "__main__":
    register()
