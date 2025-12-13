from typing import Any

from .logging import log_exc


def safe_set_hidden(elem: Any, flag: bool) -> None:
    """ビュー上の非表示状態だけを安全に切り替える。"""
    try:
        if hasattr(elem, "hide_set"):
            elem.hide_set(flag)
        elif hasattr(elem, "hide_viewport"):
            elem.hide_viewport = flag
        elif hasattr(elem, "hide"):
            elem.hide = flag
    except Exception as e:
        log_exc("safe_set_hidden", e)


def safe_get_hidden(elem: Any) -> bool:
    """ビュー上で非表示かどうかを安全に取得。"""
    try:
        if hasattr(elem, "hide_get"):
            return bool(elem.hide_get())
        if hasattr(elem, "hide_viewport"):
            return bool(elem.hide_viewport)
        if hasattr(elem, "hide"):
            return bool(elem.hide)
    except Exception:
        pass
    return False
