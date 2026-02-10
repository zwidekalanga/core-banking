"""Transaction API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi_filter import FilterDepends

from app.auth.dependencies import require_role
from app.dependencies import AppSettings, DBSession, TransactionRepo
from app.filters.transaction import TransactionFilter
from app.schemas.transaction import (
    TransactionCreate,
    TransactionCreateResponse,
    TransactionListResponse,
    TransactionResponse,
)
from app.services.transaction_service import TransactionService
from app.utils.audit import audit_logged

router = APIRouter()


@router.post(
    "",
    response_model=TransactionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin")), Depends(audit_logged("create_transaction"))],
)
async def create_transaction(
    data: TransactionCreate,
    request: Request,
    db: DBSession,
    settings: AppSettings,
) -> TransactionCreateResponse:
    """Create a transaction, persist it, evaluate via gRPC, and publish to Kafka."""
    service = TransactionService(
        db,
        settings,
        fraud_client=request.app.state.fraud_client,
        kafka_producer=getattr(request.app.state, "kafka_producer", None),
    )
    return await service.create_and_evaluate(data)


@router.get(
    "/{txn_id}",
    response_model=TransactionResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_transaction(
    txn_id: str,
    repo: TransactionRepo,
) -> TransactionResponse:
    """Get a transaction by ID."""
    txn = await repo.get_by_id(txn_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return TransactionResponse.model_validate(txn)


@router.get(
    "",
    response_model=TransactionListResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def list_transactions(
    repo: TransactionRepo,
    filters: TransactionFilter = FilterDepends(TransactionFilter),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
) -> TransactionListResponse:
    """List transactions with optional filtering and pagination."""
    transactions, total = await repo.get_all(filters, page=page, size=size)
    return TransactionListResponse.paginate(
        items=[TransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        size=size,
    )
