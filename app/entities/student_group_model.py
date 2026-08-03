from pydantic import BaseModel


class StudentGroupModel(BaseModel):
    """Группа студента. group_name = None, если связка ещё не собрана."""

    zach_number: str
    group_name: str | None
