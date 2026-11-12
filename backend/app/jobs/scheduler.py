"""APScheduler: возврат POSTPONED → UNDER_REVIEW с напоминанием; истечение ссылок; retention ПДн."""


def start_scheduler() -> None:
    """Регистрирует периодические задачи (каждые 15 минут): postponed_due, expire_sessions, retention."""


def stop_scheduler() -> None:
    pass
