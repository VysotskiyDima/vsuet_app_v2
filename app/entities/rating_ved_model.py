from pydantic import BaseModel

from app.entities.enums import VedType


class SubjectScore(BaseModel):
    score: int | str
    weight: int | str


class ControlPoint(BaseModel):
    kt_num: int
    lecture: SubjectScore
    practice: SubjectScore
    lab: SubjectScore
    other: SubjectScore
    total: int | str


class RatingVedModel(BaseModel):
    zach_number: str
    subject_name: str
    ved_type: VedType
    control_points: list[ControlPoint]
    final_rating: int | str
