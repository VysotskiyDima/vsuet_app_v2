from fastapi import APIRouter, Depends

from app.entities.enums import VedType
from app.entities.not_rating_ved_model import NotRatingVedModel
from app.entities.rating_ved_model import RatingVedModel
from app.services.rating_service import RatingService, get_rating_service


router = APIRouter(prefix="/rating", tags=["rating"])


@router.get("/{zach_number}/zachet")
async def zachet(
    zach_number: str,
    rating_service: RatingService = Depends(get_rating_service),
) -> list[RatingVedModel]:
    result = await rating_service.get_by_ved_type(zach_number, VedType.ZACHET)
    return result


@router.get("/{zach_number}/ekzamen")
async def ekzamen(
    zach_number: str,
    rating_service: RatingService = Depends(get_rating_service),
) -> list[RatingVedModel]:
    result = await rating_service.get_by_ved_type(zach_number, VedType.EKZAMEN)
    return result


@router.get("/{zach_number}/vypusknaya-rabota")
async def vypusknaya_rabota(
    zach_number: str,
    rating_service: RatingService = Depends(get_rating_service),
) -> list[NotRatingVedModel]:
    result = await rating_service.get_by_ved_type(zach_number, VedType.VYPUSKNAYA_RABOTA)
    return result


@router.get("/{zach_number}/gosekzamen")
async def gosekzamen(
    zach_number: str,
    rating_service: RatingService = Depends(get_rating_service),
) -> list[NotRatingVedModel]:
    result = await rating_service.get_by_ved_type(zach_number, VedType.GOSEKZAMEN)
    return result


@router.get("/{zach_number}/kontrolnaya-rabota")
async def kontrolnaya_rabota(
    zach_number: str,
    rating_service: RatingService = Depends(get_rating_service),
) -> list[NotRatingVedModel]:
    result = await rating_service.get_by_ved_type(zach_number, VedType.KONTROLNAYA_RABOTA)
    return result


@router.get("/{zach_number}/kursovaya-rabota")
async def kursovaya_rabota(
    zach_number: str,
    rating_service: RatingService = Depends(get_rating_service),
) -> list[NotRatingVedModel]:
    result = await rating_service.get_by_ved_type(zach_number, VedType.KURSOVAYA_RABOTA)
    return result


@router.get("/{zach_number}/kursovoy-proekt")
async def kursovoy_proekt(
    zach_number: str,
    rating_service: RatingService = Depends(get_rating_service),
) -> list[NotRatingVedModel]:
    result = await rating_service.get_by_ved_type(zach_number, VedType.KURSOVOY_PROEKT)
    return result


@router.get("/{zach_number}/praktika")
async def praktika(
    zach_number: str,
    rating_service: RatingService = Depends(get_rating_service),
) -> list[NotRatingVedModel]:
    result = await rating_service.get_by_ved_type(zach_number, VedType.PRAKTIKA)
    return result
