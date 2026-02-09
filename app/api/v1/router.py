"""API v1 router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.v1 import accounts, auth, customers, transactions

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth/admin", tags=["Auth"])
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["Accounts"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
