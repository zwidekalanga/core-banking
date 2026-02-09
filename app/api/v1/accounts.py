"""Account API endpoints."""

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import require_role
from app.dependencies import DBSession
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from app.schemas.transaction import TransactionListResponse, TransactionResponse

router = APIRouter()


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_account(
    account_id: str,
    db: DBSession,
) -> AccountResponse:
    """Get an account by ID."""
    repo = AccountRepository(db)
    account = await repo.get_by_id(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    return AccountResponse.model_validate(account)


@router.get(
    "/{account_id}/transactions",
    response_model=TransactionListResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_account_transactions(
    account_id: str,
    db: DBSession,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
) -> TransactionListResponse:
    """Get transactions for a specific account."""
    # Verify account exists
    account_repo = AccountRepository(db)
    account = await account_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    txn_repo = TransactionRepository(db)
    transactions, total = await txn_repo.get_by_account(account_id, page=page, size=size)
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        size=size,
        pages=ceil(total / size) if total > 0 else 0,
    )


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def create_account(
    data: AccountCreate,
    db: DBSession,
) -> AccountResponse:
    """Create a new account."""
    repo = AccountRepository(db)
    account = await repo.create(data)
    return AccountResponse.model_validate(account)


@router.put(
    "/{account_id}",
    response_model=AccountResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_account(
    account_id: str,
    data: AccountUpdate,
    db: DBSession,
) -> AccountResponse:
    """Update an account's status or details."""
    repo = AccountRepository(db)
    account = await repo.update(account_id, data)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    return AccountResponse.model_validate(account)
