"""Account API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import require_role
from app.dependencies import AccountRepo, TransactionRepo
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from app.schemas.transaction import TransactionListResponse, TransactionResponse
from app.utils.audit import audit_logged

router = APIRouter()


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_account(
    account_id: str,
    repo: AccountRepo,
) -> AccountResponse:
    """Get an account by ID."""
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
    account_repo: AccountRepo,
    txn_repo: TransactionRepo,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
) -> TransactionListResponse:
    """Get transactions for a specific account."""
    account = await account_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    transactions, total = await txn_repo.get_by_account(account_id, page=page, size=size)
    return TransactionListResponse.paginate(
        items=[TransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin")), Depends(audit_logged("create_account"))],
)
async def create_account(
    data: AccountCreate,
    repo: AccountRepo,
) -> AccountResponse:
    """Create a new account."""
    account = await repo.create(data)
    return AccountResponse.model_validate(account)


@router.put(
    "/{account_id}",
    response_model=AccountResponse,
    dependencies=[Depends(require_role("admin")), Depends(audit_logged("update_account"))],
)
async def update_account(
    account_id: str,
    data: AccountUpdate,
    repo: AccountRepo,
) -> AccountResponse:
    """Update an account's status or details."""
    account = await repo.update(account_id, data)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    return AccountResponse.model_validate(account)
