"""Customer API endpoints."""

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import require_role
from app.dependencies import DBSession
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerSummary,
    CustomerUpdate,
)

router = APIRouter()


@router.get(
    "",
    response_model=CustomerListResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def list_customers(
    db: DBSession,
    status_filter: str | None = Query(None, alias="status"),
    tier: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
) -> CustomerListResponse:
    """List customers with optional filtering and pagination."""
    repo = CustomerRepository(db)
    customers, total = await repo.get_all(status=status_filter, tier=tier, page=page, size=size)
    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        size=size,
        pages=ceil(total / size) if total > 0 else 0,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_customer(
    customer_id: str,
    db: DBSession,
) -> CustomerResponse:
    """Get a customer by ID."""
    repo = CustomerRepository(db)
    customer = await repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return CustomerResponse.model_validate(customer)


@router.get(
    "/{customer_id}/accounts",
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_customer_accounts(
    customer_id: str,
    db: DBSession,
):
    """Get all accounts for a customer."""
    from app.repositories.account_repository import AccountRepository
    from app.schemas.account import AccountResponse

    # Verify customer exists
    customer_repo = CustomerRepository(db)
    customer = await customer_repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    account_repo = AccountRepository(db)
    accounts = await account_repo.get_by_customer(customer_id)
    return [AccountResponse.model_validate(a) for a in accounts]


@router.get(
    "/{customer_id}/transactions",
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_customer_transactions(
    customer_id: str,
    db: DBSession,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    """Get transaction history for a customer."""
    from app.repositories.transaction_repository import TransactionRepository
    from app.schemas.transaction import TransactionListResponse, TransactionResponse

    # Verify customer exists
    customer_repo = CustomerRepository(db)
    customer = await customer_repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    txn_repo = TransactionRepository(db)
    transactions, total = await txn_repo.get_by_customer(customer_id, page=page, size=size)
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        size=size,
        pages=ceil(total / size) if total > 0 else 0,
    )


@router.get(
    "/{customer_id}/summary",
    response_model=CustomerSummary,
    dependencies=[Depends(require_role("admin", "analyst", "viewer"))],
)
async def get_customer_summary(
    customer_id: str,
    db: DBSession,
) -> CustomerSummary:
    """Get aggregated customer stats for the portal alert detail page."""
    repo = CustomerRepository(db)
    summary = await repo.get_summary(customer_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return summary


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def create_customer(
    data: CustomerCreate,
    db: DBSession,
) -> CustomerResponse:
    """Create a new customer record."""
    repo = CustomerRepository(db)
    customer = await repo.create(data)
    return CustomerResponse.model_validate(customer)


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    db: DBSession,
) -> CustomerResponse:
    """Update a customer's details."""
    repo = CustomerRepository(db)
    customer = await repo.update(customer_id, data)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return CustomerResponse.model_validate(customer)
