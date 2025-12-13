from typing import List, Tuple

import bpy

from ..core.registry import (
    HM_HideSet,
    HM_ElementRef,
    split_items_by_object,
    ensure_objects_in_edit_mode,
    add_item_unique,
)
from ..core.pid import (
    ensure_id_layers,
    assign_persistent_id_if_missing,
    build_pid_maps,
)
from ..core.bmesh_ops import (
    process_bmesh,
    hide_elements_with_rules_on_bmesh_by_pid,
)
from ..utils.safe_hidden import safe_get_hidden, safe_set_hidden
from ..utils.logging import log_exc
#追加
from ..core.diff import (
    HideSetDiffResult,
    sync_hide_set_saved_hidden,
)
from ..data.serializer import export_hide_set


class HM_ApplyHideSet(bpy.types.Operator):
    """指定した非表示セットを明示的に表示/非表示にする"""

    bl_idname = "hide_manager.apply_hide_set"
    bl_label = "非表示セットを表示 / 非表示"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty()
    list_type: bpy.props.EnumProperty(
        name="リスト",
        items=[("EDIT", "編集モード", ""), ("OBJECT", "オブジェクトモード", "")],
    )
    action: bpy.props.EnumProperty(
        name="動作",
        items=[("SHOW", "表示", ""), ("HIDE", "非表示", "")],
        default="HIDE",
    )

    def execute(self, context):
        try:
            return self._execute(context)
        except Exception as e:
            log_exc("HM_ApplyHideSet.execute", e)
            self.report({"ERROR"}, "非表示セットの適用中にエラーが発生しました")
            return {"CANCELLED"}

    def _execute(self, context):
        scene = context.scene
        hide_sets = scene.hm_object_sets if self.list_type == "OBJECT" else scene.hm_edit_sets

        if not (0 <= self.index < len(hide_sets)):
            self.report({"WARNING"}, "無効なインデックスです")
            return {"CANCELLED"}

        hide_set: HM_HideSet = hide_sets[self.index]
        hide_flag = self.action == "HIDE"

        # オブジェクトモード
        if hide_set.mode == "OBJECT":
            for it in hide_set.elements:
                obj = bpy.data.objects.get(it.object_name)
                if not obj:
                    continue
                safe_set_hidden(obj, hide_flag)

            self.report({"INFO"}, f"オブジェクトを {'非表示' if hide_flag else '表示'} にしました")
            return {"FINISHED"}

        # 編集モード（メッシュ要素）
        d = split_items_by_object(hide_set)
        if not d:
            self.report({"INFO"}, "非表示セットに要素がありません")
            return {"CANCELLED"}

        edit_objs = set(ensure_objects_in_edit_mode(context))

        for obj_name, items in d.items():
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                continue

            def _apply(bm):
                v_map, e_map, f_map, *_ = build_pid_maps(bm)
                hide_elements_with_rules_on_bmesh_by_pid(bm, items, hide_flag, v_map, e_map, f_map)

            process_bmesh(obj, edit_objs, _apply)

        self.report({"INFO"}, f"編集要素を {'非表示' if hide_flag else '表示'} にしました")
        return {"FINISHED"}


class HM_RegisterHideSet(bpy.types.Operator):
    bl_idname = "hide_manager.register_hide_set"
    bl_label = "非表示セットを登録"
    bl_options = {"REGISTER", "UNDO"}

    name: bpy.props.StringProperty(name="セット名", default="New Set")
    mode: bpy.props.EnumProperty(
        name="モード",
        items=[
            ("VERT", "頂点", ""),
            ("EDGE", "辺", ""),
            ("FACE", "面", ""),
            ("OBJECT", "オブジェクト", ""),
        ],
        default="VERT",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def execute(self, context):
        scene = context.scene

        # OBJECT モードでの登録
        if self.mode == "OBJECT":
            if context.mode != "OBJECT":
                self.report({"WARNING"}, "オブジェクトモードで実行してください")
                return {"CANCELLED"}

            selected = context.selected_objects
            if not selected:
                self.report({"INFO"}, "オブジェクトが選択されていません")
                return {"CANCELLED"}

            new_set: HM_HideSet = scene.hm_object_sets.add()
            new_set.name = self.name
            new_set.mode = "OBJECT"

            for obj in selected:
                saved = safe_get_hidden(obj)
                add_item_unique(new_set.elements, obj.name, "OBJECT", -1, saved)

            self.report({"INFO"}, f"オブジェクトを {len(selected)} 個登録しました")
            return {"FINISHED"}

        # 編集モードでの登録
        if context.mode != "EDIT_MESH":
            self.report({"WARNING"}, "編集モードで実行してください")
            return {"CANCELLED"}

        objs = ensure_objects_in_edit_mode(context)
        if not objs:
            self.report({"WARNING"}, "編集対象のオブジェクトが見つかりません")
            return {"CANCELLED"}

        new_set: HM_HideSet = scene.hm_edit_sets.add()
        new_set.name = self.name
        new_set.mode = self.mode

        total_added = 0

        for obj in objs:
            try:
                obj.update_from_editmode()
            except Exception as e:
                log_exc("HM_RegisterHideSet.update_from_editmode", e)

            def _collect(bm):
                nonlocal total_added

                v_layer, e_layer, f_layer = ensure_id_layers(bm)

                if self.mode == "VERT":
                    for v in bm.verts:
                        if not v.select:
                            continue
                        pid = assign_persistent_id_if_missing(
                            bm, v_layer, e_layer, f_layer, v, "VERT", scene
                        )
                        if add_item_unique(new_set.elements, obj.name, "VERT", pid, v.hide):
                            total_added += 1

                elif self.mode == "EDGE":
                    for e in bm.edges:
                        if not e.select:
                            continue
                        pid = assign_persistent_id_if_missing(
                            bm, v_layer, e_layer, f_layer, e, "EDGE", scene
                        )
                        if add_item_unique(new_set.elements, obj.name, "EDGE", pid, e.hide):
                            total_added += 1

                elif self.mode == "FACE":
                    for f in bm.faces:
                        if not f.select:
                            continue
                        pid = assign_persistent_id_if_missing(
                            bm, v_layer, e_layer, f_layer, f, "FACE", scene
                        )
                        if add_item_unique(new_set.elements, obj.name, "FACE", pid, f.hide):
                            total_added += 1

            process_bmesh(obj, objs, _collect)

        if total_added == 0:
            try:
                hide_sets = scene.hm_edit_sets
                hide_sets.remove(len(hide_sets) - 1)
            except Exception as e:
                log_exc("HM_RegisterHideSet.remove_empty_set", e)

            self.report({"INFO"}, "選択されている要素がありません")
            return {"CANCELLED"}

        self.report({"INFO"}, f"「{new_set.name}」を登録しました（{total_added} 要素）")
        return {"FINISHED"}


class HM_ToggleHideSet(bpy.types.Operator):
    """登録済みの非表示セットの表示/非表示をトグルする"""

    bl_idname = "hide_manager.toggle_hide_set"
    bl_label = "非表示セットをトグル"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty()
    list_type: bpy.props.EnumProperty(
        name="リスト",
        items=[("EDIT", "編集モード", ""), ("OBJECT", "オブジェクトモード", "")],
    )

    def execute(self, context):
        try:
            return self._execute(context)
        except Exception as e:
            log_exc("HM_ToggleHideSet.execute", e)
            self.report({"ERROR"}, "トグル処理中にエラーが発生しました")
            return {"CANCELLED"}

    def _execute(self, context):
        scene = context.scene
        hide_sets = scene.hm_object_sets if self.list_type == "OBJECT" else scene.hm_edit_sets

        if not (0 <= self.index < len(hide_sets)):
            self.report({"WARNING"}, "無効なインデックスです")
            return {"CANCELLED"}

        hide_set: HM_HideSet = hide_sets[self.index]

        # オブジェクトモード
        if hide_set.mode == "OBJECT":
            objs: List[Tuple[bpy.types.Object, HM_ElementRef]] = []
            for it in hide_set.elements:
                o = bpy.data.objects.get(it.object_name)
                if o:
                    objs.append((o, it))

            if not objs:
                self.report({"INFO"}, "対象のオブジェクトが見つかりません")
                return {"CANCELLED"}

            any_visible = any(not safe_get_hidden(o) for o, _ in objs)
            for o, it in objs:
                if any_visible:
                    safe_set_hidden(o, True)
                else:
                    safe_set_hidden(o, bool(it.saved_hidden))

            self.report({"INFO"}, f"オブジェクトを {'非表示' if any_visible else '表示'} にしました")
            return {"FINISHED"}

        # 編集モード
        d = split_items_by_object(hide_set)
        if not d:
            self.report({"INFO"}, "非表示セットに要素がありません")
            return {"CANCELLED"}

        edit_objs = set(ensure_objects_in_edit_mode(context))

        any_visible = False

        for obj_name, items in d.items():
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                continue

            def _check(bm):
                nonlocal any_visible
                v_map, e_map, f_map, *_ = build_pid_maps(bm)

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
                        any_visible = True
                        break

            process_bmesh(obj, edit_objs, _check)
            if any_visible:
                break

        hide_flag = any_visible

        for obj_name, items in d.items():
            obj = bpy.data.objects.get(obj_name)
            if not obj:
                continue

            def _apply(bm):
                v_map, e_map, f_map, *_ = build_pid_maps(bm)

                if hide_flag:
                    hide_elements_with_rules_on_bmesh_by_pid(bm, items, True, v_map, e_map, f_map)
                else:
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

                        if elem:
                            safe_set_hidden(elem, bool(it.saved_hidden))

            process_bmesh(obj, edit_objs, _apply)

        self.report({"INFO"}, f"編集要素を {'非表示' if hide_flag else '表示'} にしました")
        return {"FINISHED"}


class HM_RenameHideSet(bpy.types.Operator):
    bl_idname = "hide_manager.rename_hide_set"
    bl_label = "非表示セットの名前変更"

    index: bpy.props.IntProperty()
    list_type: bpy.props.EnumProperty(
        name="リスト",
        items=[("EDIT", "編集モード", ""), ("OBJECT", "オブジェクトモード", "")],
    )
    new_name: bpy.props.StringProperty(name="新しい名前", default="")

    def invoke(self, context, event):
        hide_sets = context.scene.hm_edit_sets if self.list_type == "EDIT" else context.scene.hm_object_sets
        if 0 <= self.index < len(hide_sets):
            self.new_name = hide_sets[self.index].name
        return context.window_manager.invoke_props_dialog(self, width=300)

    def execute(self, context):
        hide_sets = context.scene.hm_edit_sets if self.list_type == "EDIT" else context.scene.hm_object_sets
        if 0 <= self.index < len(hide_sets):
            hide_sets[self.index].name = self.new_name
            self.report({"INFO"}, f"名前を「{self.new_name}」に変更しました")
        return {"FINISHED"}


class HM_DeleteHideSet(bpy.types.Operator):
    bl_idname = "hide_manager.delete_hide_set"
    bl_label = "非表示セットの削除"

    index: bpy.props.IntProperty()
    list_type: bpy.props.EnumProperty(
        name="リスト",
        items=[("EDIT", "編集モード", ""), ("OBJECT", "オブジェクトモード", "")],
    )

    def execute(self, context):
        hide_sets = context.scene.hm_edit_sets if self.list_type == "EDIT" else context.scene.hm_object_sets
        if 0 <= self.index < len(hide_sets):
            try:
                hide_sets.remove(self.index)
                self.report({"INFO"}, "非表示セットを削除しました")
            except Exception as e:
                log_exc("HM_DeleteHideSet.remove", e)
                self.report({"WARNING"}, "削除に失敗しました")
                return {"CANCELLED"}
        return {"FINISHED"}

#追加
class HM_SyncHideSet(bpy.types.Operator):
    """非表示セットと現在状態を同期する（差分更新）"""

    bl_idname = "hide_manager.sync_hide_set"
    bl_label = "同期"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty()
    list_type: bpy.props.EnumProperty(
        name="リスト",
        items=[
            ("EDIT", "編集モード", ""),
            ("OBJECT", "オブジェクトモード", ""),
        ],
    )

    def execute(self, context):
        scene = context.scene
        hide_sets = scene.hm_object_sets if self.list_type == "OBJECT" else scene.hm_edit_sets

        if not (0 <= self.index < len(hide_sets)):
            self.report({"WARNING"}, "無効なインデックスです")
            return {"CANCELLED"}

        hide_set: HM_HideSet = hide_sets[self.index]

        # モードチェック（誤操作防止）
        if hide_set.mode == "OBJECT" and context.mode != "OBJECT":
            self.report({"WARNING"}, "オブジェクトモードで実行してください")
            return {"CANCELLED"}
        if hide_set.mode != "OBJECT" and context.mode != "EDIT_MESH":
            self.report({"WARNING"}, "編集モードで実行してください")
            return {"CANCELLED"}

        try:
            diff = sync_hide_set_saved_hidden(context, hide_set)
        except Exception as e:
            log_exc("HM_SyncHideSet.execute", e)
            self.report({"ERROR"}, "差分同期中にエラーが発生しました")
            return {"CANCELLED"}

        if not diff.has_changes:
            self.report({"INFO"}, "差分はありません（保存状態は最新です）")
        else:
            msg = (
                f"同期しました："
                f"更新 {diff.updated} / "
                f"削除 {diff.removed} / "
                f"追加 {diff.added}"
            )
            self.report({"INFO"}, msg)
            
        # UIの即時更新
        for area in bpy.context.window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


        return {"FINISHED"}

class HM_ExportHideSet(bpy.types.Operator):
    """HideSet を JSON ファイルへエクスポート"""

    bl_idname = "hide_manager.export_hide_set"
    bl_label = "Export"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty()
    list_type: bpy.props.EnumProperty(
        name="リスト",
        items=[
            ("EDIT", "編集モード", ""),
            ("OBJECT", "オブジェクトモード", ""),
        ],
    )

    filepath: bpy.props.StringProperty(
        subtype="FILE_PATH",
        default="hide_set.json",
    )

    def execute(self, context):
        hide_sets = (
            context.scene.hm_object_sets
            if self.list_type == "OBJECT"
            else context.scene.hm_edit_sets
        )

        if not (0 <= self.index < len(hide_sets)):
            self.report({"ERROR"}, "無効なインデックス")
            return {"CANCELLED"}

        hide_set = hide_sets[self.index]

        if export_hide_set(self.filepath, hide_set):
            self.report({"INFO"}, f"保存しました: {self.filepath}")
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, "保存に失敗しました")
            return {"CANCELLED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
