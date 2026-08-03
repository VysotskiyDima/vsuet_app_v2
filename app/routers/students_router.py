from fastapi import APIRouter, Depends

from app.entities.student_exists_model import StudentExistsModel
from app.entities.student_group_model import StudentGroupModel
from app.services.student_service import StudentService, get_student_service

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{zach_number}/exists")
async def exists(
    zach_number: str,
    student_service: StudentService = Depends(get_student_service),
) -> StudentExistsModel:
    result = await student_service.exists(zach_number)
    return result


@router.get("/{zach_number}/group")
async def group(
    zach_number: str,
    student_service: StudentService = Depends(get_student_service),
) -> StudentGroupModel:
    result = await student_service.group(zach_number)
    return result
