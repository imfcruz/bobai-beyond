"""Endpoints de cartões e solicitações de limite do protótipo."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.card import CreditLimitRequestStatus
from app.schemas.schemas import (
    CreditCardResponse,
    CreditLimitRequestCreate,
    CreditLimitRequestResponse,
    CreditLimitReviewRequest,
)
from app.services.card_service import CardService

router = APIRouter(tags=["Cards"])


def _request_response(item) -> CreditLimitRequestResponse:
    response = CreditLimitRequestResponse.model_validate(item)
    if getattr(item, "client", None) is not None:
        response.client_name = item.client.name
    return response


@router.get("/client/{client_external_id}", response_model=list[CreditCardResponse])
async def list_client_cards(client_external_id: str, db: AsyncSession = Depends(get_db)) -> list:
    return await CardService(db).list_client_cards(client_external_id)


@router.get("/limit-requests", response_model=list[CreditLimitRequestResponse])
async def list_limit_requests(
    status: CreditLimitRequestStatus | None = Query(default=None),
    client_external_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list:
    items = await CardService(db).list_limit_requests(status, client_external_id)
    return [_request_response(item) for item in items]


@router.post(
    "/limit-requests/{request_external_id}/review/{action}",
    response_model=CreditLimitRequestResponse,
)
async def review_limit_request(
    request_external_id: str,
    action: str,
    payload: CreditLimitReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    item = await CardService(db).review_limit_request(
        request_external_id, action, payload.reviewer_id, payload.reviewer_notes
    )
    return CreditLimitRequestResponse.model_validate(item)


@router.post(
    "/{card_external_id}/limit-requests",
    response_model=CreditLimitRequestResponse,
    status_code=201,
)
async def submit_limit_request(
    card_external_id: str,
    payload: CreditLimitRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    item = await CardService(db).submit_limit_request(
        card_external_id, payload.requested_limit, payload.reason
    )
    return CreditLimitRequestResponse.model_validate(item)


@router.get("/{card_external_id}", response_model=CreditCardResponse)
async def get_card(card_external_id: str, db: AsyncSession = Depends(get_db)):
    return await CardService(db).get_card(card_external_id)
