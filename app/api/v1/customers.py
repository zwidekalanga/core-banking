"""Customer API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_filter import FilterDepends

from app.auth.dependencies import require_role
from app.dependencies import AccountRepo, CustomerRepo, TransactionRepo
from app.filters.customer import CustomerFilter
from app.schemas.account import AccountResponse
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerSummary,
    CustomerUpdate,
)
from app.schemas.transaction import TransactionListResponse, TransactionResponse
from app.utils.audit import audit_logged

router = APIRouter()


@router.get(
    "",
    response_model=CustomerListResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def list_customers(
    repo: CustomerRepo,
    filters: CustomerFilter = FilterDepends(CustomerFilter),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
) -> CustomerListResponse:
    """List customers with optional filtering and pagination."""
    customers, total = await repo.get_all(filters, page=page, size=size)
    return CustomerListResponse.paginate(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_customer(
    customer_id: str,
    repo: CustomerRepo,
) -> CustomerResponse:
    """Get a customer by ID."""
    customer = await repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return CustomerResponse.model_validate(customer)


@router.get(
    "/{customer_id}/accounts",
    response_model=list[AccountResponse],
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_customer_accounts(
    customer_id: str,
    customer_repo: CustomerRepo,
    account_repo: AccountRepo,
) -> list[AccountResponse]:
    """Get all accounts for a customer."""
    customer = await customer_repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    accounts = await account_repo.get_by_customer(customer_id)
    return [AccountResponse.model_validate(a) for a in accounts]


@router.get(
    "/{customer_id}/transactions",
    response_model=TransactionListResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_customer_transactions(
    customer_id: str,
    customer_repo: CustomerRepo,
    txn_repo: TransactionRepo,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
) -> TransactionListResponse:
    """Get transaction history for a customer."""
    customer = await customer_repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    transactions, total = await txn_repo.get_by_customer(customer_id, page=page, size=size)
    return TransactionListResponse.paginate(
        items=[TransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{customer_id}/summary",
    response_model=CustomerSummary,
    dependencies=[Depends(require_role("admin", "analyst", "viewer"))],
)
async def get_customer_summary(
    customer_id: str,
    repo: CustomerRepo,
) -> CustomerSummary:
    """Get aggregated customer stats for the portal alert detail page."""
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
    dependencies=[Depends(require_role("admin")), Depends(audit_logged("create_customer"))],
)
async def create_customer(
    data: CustomerCreate,
    repo: CustomerRepo,
) -> CustomerResponse:
    """Create a new customer record."""
    customer = await repo.create(data)
    return CustomerResponse.model_validate(customer)


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(require_role("admin")), Depends(audit_logged("update_customer"))],
)
async def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    repo: CustomerRepo,
) -> CustomerResponse:
    """Update a customer's details."""
    customer = await repo.update(customer_id, data)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return CustomerResponse.model_validate(customer)
