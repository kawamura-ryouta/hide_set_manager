import bpy

from ..core.registry import get_mode_label, hide_set_is_completely_hidden
from .operators import (
    HM_ApplyHideSet,
    HM_RegisterHideSet,
)
#from ..core.diff import sync_hide_set_saved_hidden, preview_hide_set_diff
from ..core.diff import preview_hide_set_diff




class HM_PT_EditHideSets(bpy.types.Panel):
    bl_label = "非表示セット（編集モード）"
    bl_idname = "HM_PT_EditHideSets"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "非表示管理"

    @classmethod
    def poll(cls, context):
        return context.mode.startswith("EDIT")

    def draw(self, context):
        layout = self.layout
        layout.operator(HM_RegisterHideSet.bl_idname, icon="ADD")

        hide_sets = context.scene.hm_edit_sets
        if not hide_sets:
            layout.label(text="非表示セットはまだ登録されていません")
            return

        for i, hide_set in enumerate(hide_sets):
            box = layout.box()
            row = box.row(align=True)

            mode_label = get_mode_label(hide_set.mode)
            row.label(text=f"{i + 1}. {hide_set.name} [{mode_label}]")

            is_hidden = hide_set_is_completely_hidden(hide_set, context)
            


            # --- 差分判定 ---
            try:
                #diff_preview = sync_hide_set_saved_hidden(context, hide_set)
                diff_preview = preview_hide_set_diff(context, hide_set)
                needs_sync = diff_preview.has_changes
                # Panel全体の再描画
            except Exception:
                needs_sync = False

            # 同期ボタン（差分あり → エラーアイコン）
            icon = "ERROR" if needs_sync else "CHECKMARK"
            op_sync = row.operator(
                "hide_manager.sync_hide_set",
                text="同期",
                icon=icon,
            )
            op_sync.index = i
            op_sync.list_type = "EDIT"  # OBJECT側では "OBJECT" に変更



            # Export
            op = row.operator("hide_manager.export_hide_set", text="Export")
            op.index = i
            op.list_type = "EDIT" 
            

            # SHOW ボタン
            if not is_hidden:
                row.alert = True
                op_show = row.operator(HM_ApplyHideSet.bl_idname, text="", icon="HIDE_OFF")
                row.alert = False
            else:
                op_show = row.operator(HM_ApplyHideSet.bl_idname, text="", icon="HIDE_OFF")
            op_show.index = i
            op_show.list_type = "EDIT"
            op_show.action = "SHOW"

            # HIDE ボタン
            if is_hidden:
                row.alert = True
                op_hide = row.operator(HM_ApplyHideSet.bl_idname, text="", icon="HIDE_ON")
                row.alert = False
            else:
                op_hide = row.operator(HM_ApplyHideSet.bl_idname, text="", icon="HIDE_ON")
            op_hide.index = i
            op_hide.list_type = "EDIT"
            op_hide.action = "HIDE"

            # 名前変更
            op = row.operator("hide_manager.rename_hide_set", text="", icon="GREASEPENCIL")
            op.index = i
            op.list_type = "EDIT"

            # 削除
            op = row.operator("hide_manager.delete_hide_set", text="", icon="TRASH")
            op.index = i
            op.list_type = "EDIT"


class HM_PT_ObjectHideSets(bpy.types.Panel):
    bl_label = "非表示セット（オブジェクトモード）"
    bl_idname = "HM_PT_ObjectHideSets"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "非表示管理"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def draw(self, context):
        layout = self.layout
        layout.operator(HM_RegisterHideSet.bl_idname, icon="ADD")

        hide_sets = context.scene.hm_object_sets
        if not hide_sets:
            layout.label(text="非表示セットはまだ登録されていません")
            return

        for i, hide_set in enumerate(hide_sets):
            box = layout.box()
            row = box.row(align=True)

            mode_label = get_mode_label(hide_set.mode)
            row.label(text=f"{i + 1}. {hide_set.name} [{mode_label}]")

            is_hidden = hide_set_is_completely_hidden(hide_set, context)

            # --- 差分判定（UI可視化用の事前チェック） ---
            try:
                diff_preview = preview_hide_set_diff(context, hide_set)
                needs_sync = diff_preview.has_changes


            except Exception:
                needs_sync = False

            # 同期ボタン（差分あり → エラーアイコン）
            icon = "ERROR" if needs_sync else "CHECKMARK"
            op_sync = row.operator(
                "hide_manager.sync_hide_set",
                text="同期",
                icon=icon,
                emboss=True,  # ←常に普通のボタン
            )


            op_sync.index = i
            op_sync.list_type = "OBJECT" 

            # Export
            op = row.operator("hide_manager.export_hide_set", text="Export")
            op.index = i
            op.list_type = "OBJECT"  

            

            # SHOW
            if not is_hidden:
                row.alert = True
                op_show = row.operator(HM_ApplyHideSet.bl_idname, text="", icon="HIDE_OFF")
                row.alert = False
            else:
                op_show = row.operator(HM_ApplyHideSet.bl_idname, text="", icon="HIDE_OFF")
            op_show.index = i
            op_show.list_type = "OBJECT"
            op_show.action = "SHOW"

            # HIDE
            if is_hidden:
                row.alert = True
                op_hide = row.operator(HM_ApplyHideSet.bl_idname, text="", icon="HIDE_ON")
                row.alert = False
            else:
                op_hide = row.operator(HM_ApplyHideSet.bl_idname, text="", icon="HIDE_ON")
            op_hide.index = i
            op_hide.list_type = "OBJECT"
            op_hide.action = "HIDE"

            # 名前変更
            op = row.operator("hide_manager.rename_hide_set", text="", icon="GREASEPENCIL")
            op.index = i
            op.list_type = "OBJECT"

            # 削除
            op = row.operator("hide_manager.delete_hide_set", text="", icon="TRASH")
            op.index = i
            op.list_type = "OBJECT"
