import logging

logger = logging.getLogger(__name__)


def log_exc(msg: str, exc: Exception) -> None:
    """例外をログ出力。Blenderのコンソールにもフォールバックする。"""
    try:
        logger.error(f"[HideManager] {msg}: {exc}", exc_info=True)
    except Exception:
        try:
            print(f"[HideManager] {msg}: {exc}")
        except Exception:
            pass
