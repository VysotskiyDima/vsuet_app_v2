from pydantic import BaseModel


class GroupScheduleModel(BaseModel):
    """Расписание группы.

    schedule = None означает, что для группы расписание ещё не загружено, —
    это не ошибка, поэтому отвечаем 200, а не 404: клиенту достаточно отличить
    «нет данных» от «нет группы».
    """

    group_name: str
    schedule: dict | None
