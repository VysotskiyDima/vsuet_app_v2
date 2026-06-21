"""REST API: ручка на каждый тип ведомости + /exists.

Все ручки по типам возвращают 200 + массив (возможно пустой). /exists возвращает
{"exists": bool}. Поиск идёт по префиксу <zach_number>:<ved_type>:* в активной БД.
"""



from fastapi import APIRouter, Depends, Request, Path

from app.entities.enums import VedType
from app.repository.redis_repository import RedisRepository
from app.services.student_service import StudentService


router = APIRouter(prefix="/students", tags=["students"])


def get_student_service(request: Request) -> StudentService:
    repo: RedisRepository = request.app.state.repo
    return StudentService(repo)


@router.get("/{zach_number}/exists")
async def exists(
    zach_number: str = Path(
        ...,
        openapi_examples={
            "default": {
                "summary": "Sample gradebook",
                "value": "247162",
            }
        },
    ),
    service: StudentService = Depends(get_student_service),
) -> dict:
    return {"exists": await service.exists(zach_number)}


@router.get("/{zach_number}/zachet")
async def zachet(
    zach_number: str = Path(
        ...,
        openapi_examples={
            "default": {
                "summary": "Sample gradebook",
                "value": "247162",
            }
        },
    ),
    service: StudentService = Depends(get_student_service),
) -> list[dict]:
    return await service.get_by_ved_type(zach_number, VedType.ZACHET)


@router.get("/{zach_number}/ekzamen")
async def ekzamen(
    zach_number: str = Path(
        ...,
        openapi_examples={
            "default": {
                "summary": "Sample gradebook",
                "value": "247162",
            }
        },
    ),
    service: StudentService = Depends(get_student_service),
) -> list[dict]:
    return await service.get_by_ved_type(zach_number, VedType.EKZAMEN)


@router.get("/{zach_number}/vypusknaya-rabota")
async def vypusknaya_rabota(
    zach_number: str = Path(
        ...,
        openapi_examples={
            "default": {
                "summary": "Sample gradebook",
                "value": "247162",
            }
        },
    ),
    service: StudentService = Depends(get_student_service),
) -> list[dict]:
    return await service.get_by_ved_type(zach_number, VedType.VYPUSKNAYA_RABOTA)


@router.get("/{zach_number}/gosekzamen")
async def gosekzamen(
    zach_number: str = Path(
        ...,
        openapi_examples={
            "default": {
                "summary": "Sample gradebook",
                "value": "247162",
            }
        },
    ),
    service: StudentService = Depends(get_student_service),
) -> list[dict]:
    return await service.get_by_ved_type(zach_number, VedType.GOSEKZAMEN)


@router.get("/{zach_number}/kontrolnaya-rabota")
async def kontrolnaya_rabota(
    zach_number: str = Path(
        ...,
        openapi_examples={
            "default": {
                "summary": "Sample gradebook",
                "value": "247162",
            }
        },
    ),
    service: StudentService = Depends(get_student_service),
) -> list[dict]:
    return await service.get_by_ved_type(zach_number, VedType.KONTROLNAYA_RABOTA)


@router.get("/{zach_number}/kursovaya-rabota")
async def kursovaya_rabota(
    zach_number: str = Path(
        ...,
        openapi_examples={
            "default": {
                "summary": "Sample gradebook",
                "value": "247162",
            }
        },
    ),
    service: StudentService = Depends(get_student_service),
) -> list[dict]:
    return await service.get_by_ved_type(zach_number, VedType.KURSOVAYA_RABOTA)


@router.get("/{zach_number}/kursovoy-proekt")
async def kursovoy_proekt(
    zach_number: str = Path(
        ...,
        openapi_examples={
            "default": {
                "summary": "Sample gradebook",
                "value": "247162",
            }
        },
    ),
    service: StudentService = Depends(get_student_service),
) -> list[dict]:
    return await service.get_by_ved_type(zach_number, VedType.KURSOVOY_PROEKT)


@router.get("/{zach_number}/praktika")
async def praktika(
    zach_number: str = Path(
        ...,
        openapi_examples={
            "default": {
                "summary": "Sample gradebook",
                "value": "247162",
            }
        },
    ),
    service: StudentService = Depends(get_student_service),
) -> list[dict]:
    return await service.get_by_ved_type(zach_number, VedType.PRAKTIKA)
