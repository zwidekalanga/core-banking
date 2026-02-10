# Principal Engineer Code Review: Core Banking Service

**Reviewer**: Principal Engineer (Automated Deep Review)
**Date**: 2026-02-09
**Scope**: Full codebase — architecture, code quality, security, testing, FastAPI alignment, design patterns
**Codebase Size**: ~80KB across 34 Python modules, ~60 tests

---

## Overall Rating: 6.8 / 10

| Category | Score | Weight | Weighted |
|---|---|---|---|
| Architecture & Separation of Concerns | 7.5 | 20% | 1.50 |
| Code Quality (SOLID, DRY, Readability) | 7.0 | 20% | 1.40 |
| Security & Hardening | 5.5 | 15% | 0.83 |
| Error Handling & Resilience | 6.0 | 10% | 0.60 |
| Testing Strategy & Coverage | 5.0 | 15% | 0.75 |
| FastAPI Best Practices Alignment | 7.5 | 10% | 0.75 |
| Design Patterns & Extensibility | 7.0 | 10% | 0.70 |
| **Weighted Total** | | **100%** | **6.53** |

**Verdict**: Solid foundation, but not yet production-grade. The architectural skeleton is clean and follows the same proven patterns as `core-fraud-detection`, but several critical gaps — particularly in security hardening, error handling, testing coverage, and the dependency injection lifecycle — need to be addressed before this service handles real financial data.

---

## 1. Architecture & Separation of Concerns — 7.5/10

### What's Done Well

**Clean Layered Structure** — The same disciplined layering as `core-fraud-detection`:

```
API Layer (app/api/v1/)        ← HTTP contract, validation, auth
    ↓
Repository Layer (app/repositories/)  ← Data access abstraction
    ↓
Model Layer (app/models/)      ← ORM entities
```

Schemas (Pydantic) are separated from models (SQLAlchemy). Route handlers never construct raw SQL. This is correct.

**API Design** — RESTful resource hierarchy is well-structured:
- `/customers/{id}/accounts` — sub-resource for customer's accounts
- `/customers/{id}/transactions` — sub-resource for customer's transactions
- `/customers/{id}/summary` — aggregated analytics endpoint
- `/accounts/{id}/transactions` — sub-resource for account's transactions

This is clean REST modelling that avoids both over-nesting and flat-URL chaos.

**Shared Base Classes** — `UUIDMixin`, `TimestampMixin`, and `Base` are reused identically with `core-fraud-detection`, ensuring schema consistency across services.

**`PaginatedResponse` Base Schema** — `schemas/common.py` provides a reusable base for paginated lists, and `CustomerListResponse`, `TransactionListResponse` extend it cleanly.

### Issues

**ARCH-001: Missing service layer (Medium)**

The `app/services/` directory contains only `kafka_producer.py`. All business logic lives directly in route handlers. Compare this with `core-fraud-detection` which has `FraudEvaluationService` as an orchestration facade.

The `create_transaction` endpoint in `transactions.py:25-95` contains 70 lines of orchestration logic (persist → gRPC eval → Kafka publish). This should be a `TransactionService`:

```python
# app/services/transaction_service.py
class TransactionService:
    def __init__(self, session: AsyncSession, fraud_client, kafka_producer):
        ...

    async def create_and_evaluate(self, data: TransactionCreate) -> TransactionCreateResponse:
        txn = await self._repo.create(data)
        fraud_result = await self._evaluate_fraud(txn)
        await self._publish_event(txn)
        return self._build_response(txn, fraud_result)
```

**Why this matters**: The current structure means the transaction creation flow can only be invoked via HTTP. If you later need to create transactions from a batch import, Kafka consumer, or CLI script, you'd duplicate the orchestration logic.

**ARCH-002: Inline imports in route handlers (Low)**

`customers.py:67-68` and `customers.py:87-88` use inline imports inside handler functions:

```python
async def get_customer_accounts(...):
    from app.repositories.account_repository import AccountRepository  # inline
    from app.schemas.account import AccountResponse  # inline
```

This suggests a circular import was encountered and worked around. Inline imports are a code smell — they indicate the module dependency graph has a cycle that should be resolved architecturally.

**ARCH-003: No `InfrastructureContainer` for non-FastAPI paths (Low)**

Unlike `core-fraud-detection`, there's no equivalent of `InfrastructureContainer` for gRPC or Kafka consumer contexts. Currently not needed since this service only has HTTP, but it limits future extensibility.

---

## 2. Code Quality — 7.0/10

### SOLID Principles

| Principle | Adherence | Notes |
|---|---|---|
| **S** — Single Responsibility | Moderate | Route handlers do too much (especially `create_transaction`). Repositories are clean. |
| **O** — Open/Closed | Moderate | No extension points for the transaction pipeline. Adding a new step (e.g., balance check) requires modifying the handler. |
| **L** — Liskov Substitution | Good | `PaginatedResponse` base class properly extended by list responses. |
| **I** — Interface Segregation | Good | `CurrentUser`, `DBSession`, `RedisClient` type aliases are focused. |
| **D** — Dependency Inversion | Moderate | Repositories depend on concrete schemas (`CustomerCreate`). Kafka producer and gRPC client are module-level singletons, not injected. |

### DRY Analysis

**Good**:
- `PaginatedResponse` eliminates repeated pagination fields
- `TimestampMixin` and `UUIDMixin` reuse across all models
- `TransactionRepository.get_by_customer()` and `get_by_account()` delegate to `get_all()` — proper DRY
- `model_dump(exclude_unset=True)` pattern reused for partial updates

**Violations**:

**CQ-001: Pagination calculation repeated in every list endpoint (Medium)**

```python
# Appears in 5 endpoints identically:
pages=ceil(total / size) if total > 0 else 0,
```

This should be a method on `PaginatedResponse`:

```python
class PaginatedResponse(BaseModel):
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def paginate(cls, items, total, page, size, **kwargs):
        return cls(
            items=items, total=total, page=page, size=size,
            pages=ceil(total / size) if total > 0 else 0,
            **kwargs,
        )
```

**CQ-002: Filter application duplicated across repositories (Medium)**

`TransactionRepository.get_all()` and `CustomerRepository.get_all()` both manually duplicate filter logic between the data query and count query. `core-fraud-detection` solved this with `_apply_filters()`. Apply the same pattern here:

```python
def _apply_filters(self, query, **kwargs):
    if kwargs.get("customer_id"):
        query = query.where(Transaction.customer_id == kwargs["customer_id"])
    ...
    return query
```

**CQ-003: f-string logging (Low)**

Multiple files use f-string interpolation in logging calls:

```python
# transactions.py:73
logger.info(f"Fraud evaluation for {txn.external_id}: ...")
# kafka_producer.py:36
logger.info(f"Published transaction {key} to {TOPIC_TRANSACTIONS_RAW}")
```

This evaluates the string even when the log level is suppressed. Use lazy formatting:

```python
logger.info("Fraud evaluation for %s: score=%d decision=%s", txn.external_id, ...)
```

**CQ-004: `get_customer_accounts` and `get_customer_transactions` missing `response_model` (Low)**

```python
@router.get("/{customer_id}/accounts", ...)
async def get_customer_accounts(...):  # No response_model
    ...
```

These endpoints lack `response_model`, making the OpenAPI spec incomplete. Add `response_model=list[AccountResponse]` and `response_model=TransactionListResponse`.

---

## 3. Security & Hardening — 5.5/10

### What's Done Well

- **RBAC enforcement**: `require_role()` applied to every endpoint
- **JWT shared secret**: Same HS256 secret with `core-fraud-detection` enables stateless cross-service auth
- **Password hashing**: bcrypt with `gensalt()` — correct
- **Token type validation**: Access tokens rejected at refresh endpoint and vice versa
- **User activity check**: Refresh flow verifies `user.is_active` before issuing new tokens
- **Pydantic input validation**: `Field(gt=0)` on amounts, `min_length` on IDs

### Issues — These are significant for a banking service

**SEC-001: No JWT secret strength enforcement (High)**

Unlike `core-fraud-detection` which has `enforce_jwt_secret_strength` rejecting weak secrets in staging/production, `core-banking` has NO validation:

```python
# config.py:44 — no validator, no warning
jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"
```

This means the service will happily start in production with the default placeholder secret.

**Fix**: Port the `enforce_jwt_secret_strength` model validator from `core-fraud-detection`:
```python
@model_validator(mode="after")
def enforce_jwt_secret_strength(self) -> "Settings":
    if self.environment != "development":
        if self.jwt_secret_key == "CHANGE-ME-IN-PRODUCTION":
            raise ValueError("jwt_secret_key must be changed in staging/production")
        if len(self.jwt_secret_key) < 32:
            raise ValueError("jwt_secret_key must be >= 32 characters")
    return self
```

**SEC-002: No security headers middleware (High)**

`core-fraud-detection` adds `SecurityHeadersMiddleware` (X-Frame-Options, HSTS, CSP, X-Content-Type-Options, Referrer-Policy). `core-banking` has **none**. For a service that handles PII (names, ID numbers, dates of birth), this is a significant omission.

**Fix**: Copy the `SecurityHeadersMiddleware` from `core-fraud-detection/app/main.py`.

**SEC-003: No request ID middleware (Medium)**

No `X-Request-ID` injection for distributed tracing. When a transaction spans core-banking → gRPC → core-fraud-detection, there's no correlation ID. Debugging production issues will be extremely difficult.

**Fix**: Copy the `RequestIDMiddleware` from `core-fraud-detection/app/main.py`.

**SEC-004: No rate limiting (Medium)**

No SlowAPI or equivalent rate limiting. The `/auth/admin/login` endpoint is vulnerable to brute-force credential stuffing.

**Fix**: Add `slowapi` as in `core-fraud-detection`.

**SEC-005: No global exception handler (Medium)**

There is no catch-all exception handler. An unhandled exception will return FastAPI's default 500 response, which includes the Python traceback in debug mode and may leak internal details.

**Fix**:
```python
@app.exception_handler(Exception)
async def _unhandled_exception_handler(request, exc):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

**SEC-006: CORS allows all methods and headers (Medium)**

```python
# main.py:47-48
allow_methods=["*"],
allow_headers=["*"],
```

Compare with `core-fraud-detection` which explicitly lists:
```python
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
```

Wildcard CORS headers are unnecessarily permissive for a banking API.

**SEC-007: No audit logging (Medium)**

`core-fraud-detection` has `audit_logged()` on every state-changing endpoint. `core-banking` has no audit trail. For a service that creates customers, accounts, and transactions, this is a compliance gap. Financial regulators require audit trails.

**SEC-008: `AccountUpdate` allows direct balance modification (High)**

```python
class AccountUpdate(BaseModel):
    status: str | None = None
    balance: Decimal | None = None  # Directly writable!
```

The `PUT /accounts/{id}` endpoint allows an admin to directly set any account balance to any value. In a real banking system, balances should only change through transactions (double-entry bookkeeping). Direct balance writes bypass all audit trails and enable embezzlement.

**Fix**: Remove `balance` from `AccountUpdate`. Balances should be computed from the transaction ledger, or at minimum, balance modifications should be a separate, heavily-audited endpoint.

**SEC-009: No input validation for enum fields on create schemas (Low)**

`CustomerCreate` accepts raw strings for `kyc_status`, `tier`, `risk_rating`, `status` without validating against the enum values:

```python
kyc_status: str = "pending"  # Accepts any string, not validated against KYCStatus enum
tier: str = "standard"       # Same
```

A request with `{"tier": "platinum"}` would be persisted to the database. Use the enum types:
```python
kyc_status: KYCStatus = KYCStatus.pending
tier: CustomerTier = CustomerTier.standard
```

---

## 4. Error Handling & Resilience — 6.0/10

### What's Done Well

- **Best-effort gRPC and Kafka**: `create_transaction` wraps both gRPC and Kafka calls in try/except and logs warnings rather than failing the transaction creation. This is the correct design — the transaction should persist even if downstream services are unavailable.
- **404 handling**: All get-by-id endpoints properly return 404 with clear messages.
- **Auth error codes**: Login returns 401 for bad credentials, 403 for disabled accounts.

### Issues

**ERR-001: `get_db_session` does not commit or rollback (High)**

```python
# dependencies.py:39-44
async def get_db_session(...):
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
```

Compare with `core-fraud-detection`:
```python
async def get_db_session(...):
    async with session_factory() as session:
        try:
            yield session
            await session.commit()   # ← commits on success
        except Exception:
            await session.rollback() # ← rolls back on error
            raise
        finally:
            await session.close()
```

The `core-banking` version does NOT commit or rollback. Instead, **every repository method calls `session.commit()` individually**. This means:

1. **No atomic multi-repository operations** — If `create_transaction` needs to update an account balance AND create a transaction, they commit independently. A failure between commits leaves the database in an inconsistent state.
2. **No automatic rollback on exception** — If an exception occurs after a repository commit, partial data persists.

**Fix**: Adopt the Unit of Work pattern from `core-fraud-detection`:
```python
async def get_db_session(...):
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

Then change all repository methods from `commit()` to `flush()`.

**ERR-002: Readiness check is fake (High)**

```python
# main.py:65-73
async def readiness_check() -> dict:
    checks = {
        "database": "ok",   # Always "ok" — never actually checks!
        "redis": "ok",      # Always "ok" — never actually checks!
    }
```

Compare with `core-fraud-detection` which actually executes `SELECT 1` against the DB and `redis.ping()`. The core-banking readiness endpoint always returns "ready" even if the database is down. Kubernetes would route traffic to an unhealthy pod.

**Fix**:
```python
async def readiness_check(request: Request):
    checks = {}
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    # ... return 503 if degraded
```

**ERR-003: Kafka producer never shut down (Medium)**

`kafka_producer.py` defines `close_kafka_producer()` but it's never called. The lifespan manager in `main.py` only logs — it doesn't close the Kafka producer or Redis client or database engine.

```python
# main.py:20-24 — lifespan does nothing on shutdown
async def lifespan(_app: FastAPI):
    logger.info("Starting...")
    yield
    logger.info("Shutting down...")  # No cleanup!
```

**Fix**: Add cleanup to lifespan:
```python
async def lifespan(app: FastAPI):
    engine = get_engine(settings)
    app.state.engine = engine
    app.state.session_factory = get_session_factory(settings)
    yield
    from app.services.kafka_producer import close_kafka_producer
    await close_kafka_producer()
    await engine.dispose()
```

**ERR-004: `CustomerSummary.onboarded_at` can throw if None (Low)**

```python
# customer_repository.py:83
account_age_days = (datetime.now(UTC) - customer.onboarded_at).days
```

If `onboarded_at` is somehow `None` (data corruption), this crashes with a `TypeError`. The model marks `onboarded_at` as non-nullable, but defensive coding would handle this:

```python
account_age_days = (datetime.now(UTC) - customer.onboarded_at).days if customer.onboarded_at else 0
```

---

## 5. Testing Strategy & Coverage — 5.0/10

### What Exists

- **3 unit test files**: `test_auth.py`, `test_models.py`, `test_schemas.py`
- **~60 test methods** covering authentication, enums, and schema validation
- **Empty integration test directory** — placeholder only

### What's Good

- Settings cache clearing fixture (`_clear_settings_cache`) ensures test isolation
- Auth tests cover password hashing, token creation/validation, expiry, and wrong-secret rejection
- Schema tests validate boundary conditions (positive amounts, min lengths, defaults)
- Enum tests verify completeness with member counts

### What's Missing — Critical Gaps

**TEST-001: Zero API endpoint tests (High)**

No HTTP integration tests exist. The entire API surface — 14 endpoints across auth, customers, accounts, and transactions — is untested. This includes:
- RBAC enforcement (can a viewer create a customer?)
- Pagination behavior
- 404 responses for missing resources
- The critical `create_transaction` orchestration flow

Compare with `core-fraud-detection` which has 19 integration tests covering the full API surface.

**Fix**: Add `tests/integration/test_http_api.py` using `httpx.AsyncClient`:
```python
async def test_viewer_cannot_create_customer(viewer_client):
    resp = await viewer_client.post("/api/v1/customers", json={...})
    assert resp.status_code == 403
```

**TEST-002: Zero repository tests (High)**

No tests verify that SQL queries return correct results. Filter logic, pagination, sorting, and the `get_summary()` aggregation query are all untested.

**TEST-003: Zero gRPC client tests (Medium)**

The `FraudEvaluationClient` is untested — no mock gRPC channel, no timeout handling, no error path coverage.

**TEST-004: Zero Kafka producer tests (Medium)**

`publish_transaction()` is untested — no verification that messages are serialized correctly or that the key is set properly.

**TEST-005: No conftest fixtures for API testing (Medium)**

The `conftest.py` only clears settings cache. There are no fixtures for:
- HTTP client (`AsyncClient` against the FastAPI app)
- Authenticated clients (admin/analyst/viewer)
- Mock database sessions
- Fake Redis

### Test Coverage Estimate

| Area | Tested | Untested |
|---|---|---|
| Password hashing | Yes | — |
| JWT tokens | Yes | — |
| Pydantic schemas | Yes | — |
| Model enums | Yes | — |
| API endpoints (14) | No | All 14 |
| Repositories (4) | No | All 4 |
| gRPC client | No | All |
| Kafka producer | No | All |
| Transaction orchestration | No | All |
| RBAC enforcement | No | All |

**Estimated line coverage**: ~25-30% (auth + schemas + models only)

---

## 6. FastAPI Best Practices Alignment — 7.5/10

### What's Done Well

| Practice | Status | Evidence |
|---|---|---|
| Application factory pattern | Implemented | `create_application()` |
| Lifespan manager (not `@on_event`) | Implemented | `@asynccontextmanager async def lifespan()` |
| Annotated dependency types | Implemented | `DBSession`, `RedisClient`, `AppSettings` |
| Pydantic v2 with `model_config` | Implemented | `from_attributes=True` |
| API versioning | Implemented | `/api/v1/` prefix |
| Query parameter validation | Implemented | `Query(ge=1, le=100)` |
| Status codes | Correct | 201 for create, 404 for not found |
| OpenAPI docs | Configured | `/docs`, `/redoc` |
| Dependency-based auth | Implemented | `require_role()` factory |
| `@lru_cache` settings | Implemented | `get_settings()` |
| OAuth2 form login | Implemented | `OAuth2PasswordRequestForm` |

### Issues

**FAPI-001: Module-level mutable singletons for infrastructure (High)**

```python
# dependencies.py:12-13
_engine = None
_session_factory = None

# dependencies.py:52
_redis_client = None
```

These module-level globals with lazy initialization are problematic:

1. **Untestable** — You can't override them with `app.dependency_overrides` because they're not FastAPI dependencies; they're hidden behind regular functions.
2. **No cleanup** — There's no shutdown path. The engine, session factory, and Redis client are never disposed.
3. **Thread-safety** — Multiple concurrent requests on startup could create multiple engines (race condition on `if _engine is None`).

Compare with `core-fraud-detection` which uses `app.state` + lifespan:
```python
# In lifespan:
app.state.engine = create_engine(settings)
app.state.session_factory = create_session_factory(engine)
app.state.redis = create_redis(settings)
# In dependency:
session_factory = request.app.state.session_factory
```

**Fix**: Move resource creation to the lifespan manager and pull from `request.app.state` in dependencies, exactly as `core-fraud-detection` does.

**FAPI-002: Kafka producer uses module-level global singleton (Medium)**

```python
# kafka_producer.py:11
_producer: AIOKafkaProducer | None = None
```

Same problem as FAPI-001. The producer is lazily created on first use and never injected via FastAPI's DI system. This makes it impossible to mock in tests without patching.

**FAPI-003: gRPC client uses module-level global singleton (Medium)**

```python
# fraud_client.py:67
_client: FraudEvaluationClient | None = None
```

Same pattern, same problems. Additionally, the target is read from `os.environ.get()` instead of from `Settings`, breaking the pydantic-settings contract.

---

## 7. Design Patterns Assessment (refactoring.guru Catalog)

### Patterns Already Implemented

| Pattern | Category | Implementation | Quality |
|---|---|---|---|
| **Repository** | — | `CustomerRepository`, `AccountRepository`, `TransactionRepository`, `UserRepository` | Good — clean data access abstraction |
| **Factory Method** | Creational | `create_application()`, `get_engine()`, `get_session_factory()` | Adequate — but singleton lifecycle is flawed (FAPI-001) |
| **Template Method** (Partial) | Behavioral | `PaginatedResponse` base → `CustomerListResponse`, `TransactionListResponse` | Good — proper schema inheritance |

### Patterns Missing (Compared to core-fraud-detection)

| Pattern | Where It's Missing | Impact |
|---|---|---|
| **Facade** | No `TransactionService` to orchestrate persist → evaluate → publish | Route handler is 70 lines of orchestration (ARCH-001) |
| **Builder** | No `TransactionFilter` dataclass like `AlertFilter` | Filter params passed as raw kwargs (CQ-002) |
| **State** | No status transition validation for accounts or customers | Any status string accepted — `active` → `banana` is valid |
| **Decorator** | No `audit_logged()` cross-cutting concern | No audit trail (SEC-007) |

### Patterns Applicable — Recommendations

#### **Facade** — Strongly Recommended (Priority: High)

**Where**: `create_transaction` handler in `transactions.py:25-95`

**Current**: 70-line handler with inline gRPC import, inline Kafka import, nested try/except blocks.

**Proposed**:
```python
class TransactionService:
    def __init__(self, session, fraud_client, kafka_producer):
        self._repo = TransactionRepository(session)
        self._fraud = fraud_client
        self._kafka = kafka_producer

    async def create_and_evaluate(self, data: TransactionCreate) -> TransactionCreateResponse:
        txn = await self._repo.create(data)
        fraud = await self._evaluate(txn)
        await self._publish(txn)
        return self._response(txn, fraud)
```

**FastAPI compatibility**: Full. Register as a FastAPI dependency via `Depends()`.

#### **Builder** — Recommended (Priority: Medium)

**Where**: `TransactionRepository.get_all()` and `CustomerRepository.get_all()`

**Proposed**: Typed filter dataclass like `core-fraud-detection`'s `AlertFilter`:
```python
@dataclass
class TransactionFilter:
    customer_id: str | None = None
    account_id: str | None = None
    type: str | None = None
    channel: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    page: int = 1
    size: int = 50
```

**FastAPI compatibility**: Full.

#### **State** — Recommended (Priority: Medium)

**Where**: Customer status, account status, and transaction status transitions are unvalidated.

**Proposed**: Same pattern as `core-fraud-detection`'s `VALID_STATUS_TRANSITIONS`:
```python
VALID_ACCOUNT_TRANSITIONS = {
    "active": {"frozen", "dormant", "closed"},
    "frozen": {"active", "closed"},
    "dormant": {"active", "closed"},
    "closed": set(),  # terminal
}
```

**FastAPI compatibility**: Full.

#### **Observer** — Future Consideration

**Where**: When a customer's `risk_rating` changes to `high`, the fraud-detection service should be notified to adjust its scoring thresholds for that customer.

**Implementation**: Redis pub/sub or Kafka topic for customer risk change events.

**FastAPI compatibility**: Full.

### Patterns That Would Break FastAPI Conventions

Same guidance as `core-fraud-detection` review — avoid class-based Singleton, Service Locator, Active Record, and MediatR-style Mediator in FastAPI.

---

## 8. Specific Code Fixes

### Fix 1: Session lifecycle — adopt Unit of Work (ERR-001) — Priority: Critical

**File**: `app/dependencies.py`

```python
# REPLACE get_db_session with:
async def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory(settings)
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

Then change all repository `commit()` calls to `flush()`.

### Fix 2: Real readiness check (ERR-002) — Priority: Critical

**File**: `app/main.py`

```python
@app.get("/ready", tags=["Health"])
async def readiness_check(request: Request):
    checks: dict[str, str] = {}
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    all_ok = all(v == "ok" for v in checks.values())
    if not all_ok:
        return JSONResponse(status_code=503, content={"status": "degraded", "checks": checks})
    return {"status": "ready", "checks": checks}
```

### Fix 3: JWT secret strength validation (SEC-001) — Priority: High

**File**: `app/config.py`

```python
from pydantic import model_validator

@model_validator(mode="after")
def enforce_jwt_secret_strength(self) -> "Settings":
    if self.environment != "development":
        if self.jwt_secret_key == "CHANGE-ME-IN-PRODUCTION":
            raise ValueError("jwt_secret_key must be changed in staging/production")
        if len(self.jwt_secret_key) < 32:
            raise ValueError("jwt_secret_key must be >= 32 characters")
    return self
```

### Fix 4: Security headers middleware (SEC-002) — Priority: High

**File**: `app/main.py` — Copy `SecurityHeadersMiddleware` and `RequestIDMiddleware` from `core-fraud-detection`.

### Fix 5: Remove balance from AccountUpdate (SEC-008) — Priority: High

**File**: `app/schemas/account.py`

```python
class AccountUpdate(BaseModel):
    status: str | None = None
    # balance removed — must be changed through transactions only
```

### Fix 6: Global exception handler (SEC-005) — Priority: Medium

**File**: `app/main.py`

```python
@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

### Fix 7: Restrict CORS (SEC-006) — Priority: Medium

**File**: `app/main.py`

```python
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
```

### Fix 8: Enum validation on create schemas (SEC-009) — Priority: Medium

**File**: `app/schemas/customer.py`

```python
from app.models.customer import KYCStatus, CustomerTier, RiskRating, CustomerStatus

class CustomerCreate(BaseModel):
    kyc_status: KYCStatus = KYCStatus.pending
    tier: CustomerTier = CustomerTier.standard
    risk_rating: RiskRating = RiskRating.low
    status: CustomerStatus = CustomerStatus.active
```

### Fix 9: Lifespan resource cleanup (ERR-003) — Priority: Medium

**File**: `app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine(get_settings())
    app.state.engine = engine
    app.state.session_factory = get_session_factory(get_settings())
    app.state.redis = await get_redis_client(get_settings())
    logger.info("Core Banking Service started")
    yield
    from app.services.kafka_producer import close_kafka_producer
    from app.grpc.fraud_client import get_fraud_client
    await close_kafka_producer()
    await get_fraud_client().close()
    await app.state.redis.aclose()
    await engine.dispose()
    logger.info("Core Banking Service stopped")
```

---

## 9. Summary of All Issues

| ID | Severity | Category | Description | Effort |
|---|---|---|---|---|
| ERR-001 | **Critical** | Error Handling | `get_db_session` doesn't commit/rollback — no Unit of Work | 1h |
| ERR-002 | **Critical** | Resilience | Readiness check is hardcoded "ok" — never checks DB/Redis | 30min |
| SEC-001 | **High** | Security | No JWT secret strength enforcement in staging/prod | 15min |
| SEC-002 | **High** | Security | No security headers middleware (HSTS, CSP, X-Frame-Options) | 30min |
| SEC-008 | **High** | Security | `AccountUpdate` allows direct balance writes | 10min |
| FAPI-001 | **High** | FastAPI | Module-level mutable singletons (engine, session, redis) | 2h |
| TEST-001 | **High** | Testing | Zero API endpoint tests (14 endpoints untested) | 6-8h |
| TEST-002 | **High** | Testing | Zero repository tests | 4-6h |
| ARCH-001 | Medium | Architecture | No service layer — 70-line handler orchestration | 2-3h |
| SEC-003 | Medium | Security | No X-Request-ID middleware for tracing | 15min |
| SEC-004 | Medium | Security | No rate limiting on login endpoint | 30min |
| SEC-005 | Medium | Security | No global exception handler — may leak internals | 15min |
| SEC-006 | Medium | Security | CORS allows all methods and headers | 5min |
| SEC-007 | Medium | Security | No audit logging on state-changing endpoints | 2h |
| SEC-009 | Medium | Security | Enum fields accept arbitrary strings | 30min |
| ERR-003 | Medium | Resilience | Kafka producer never closed on shutdown | 30min |
| CQ-001 | Medium | Code Quality | Pagination calculation duplicated 5 times | 30min |
| CQ-002 | Medium | Code Quality | Filter logic duplicated between data/count queries | 1h |
| FAPI-002 | Medium | FastAPI | Kafka producer is module-level singleton | 1h |
| FAPI-003 | Medium | FastAPI | gRPC client is module-level singleton | 1h |
| TEST-003 | Medium | Testing | Zero gRPC client tests | 2h |
| TEST-004 | Medium | Testing | Zero Kafka producer tests | 1h |
| ARCH-002 | Low | Architecture | Inline imports to avoid circular dependencies | 30min |
| CQ-003 | Low | Code Quality | f-string in logging calls (eager evaluation) | 30min |
| CQ-004 | Low | Code Quality | Missing `response_model` on 2 endpoints | 10min |

**Critical**: 2 | **High**: 5 | **Medium**: 14 | **Low**: 3

---

## 10. Comparison with core-fraud-detection

| Aspect | core-fraud-detection (8.4) | core-banking (6.8) | Delta |
|---|---|---|---|
| Session lifecycle | Unit of Work (commit/rollback in dependency) | Each repo commits individually | -1.5 |
| Security headers | Full middleware stack | None | -2.0 |
| Rate limiting | SlowAPI 120/min | None | -1.0 |
| JWT enforcement | Model validator rejects weak secrets | No validation | -1.5 |
| Exception handler | Global catch-all, never leaks | None | -1.0 |
| Readiness check | Actually checks DB + Redis | Hardcoded "ok" | -2.0 |
| Audit logging | `audit_logged()` on all writes | None | -1.5 |
| Test coverage | 150 tests (unit + integration) | ~60 tests (unit only) | -2.0 |
| Service layer | `FraudEvaluationService` facade | Logic in handlers | -1.0 |
| Resource lifecycle | Lifespan manages engine, redis | Module-level globals | -1.5 |
| CORS | Explicit methods/headers | Wildcards | -0.5 |

The gap is primarily in **operational hardening** — the features that make a service production-safe. The architectural skeleton and code organization are sound.

---

## 11. What's Done Well

1. **Clean API hierarchy** — Sub-resource routes (`/customers/{id}/accounts`) follow REST conventions correctly.
2. **`CustomerSummary` aggregation** — The `get_summary()` repository method with SQL aggregations (COUNT, SUM, AVG) over a 30-day window is well-implemented and serves the fraud ops portal's alert detail page efficiently.
3. **Transaction → Fraud evaluation pipeline** — The best-effort pattern (persist first, evaluate asynchronously, don't fail on downstream errors) is the correct architecture for a banking transaction service.
4. **Schema inheritance** — `TransactionCreateResponse` extends `TransactionResponse` with an optional `fraud_evaluation` field. `PaginatedResponse` base class is properly reused. This is clean Pydantic design.
5. **Auth token lifecycle** — Login, refresh, and `/me` endpoints form a complete token lifecycle. The refresh endpoint re-validates `user.is_active`, preventing revoked users from getting new tokens.
6. **IP address handling** — `TransactionResponse` uses `@field_serializer("ip_address")` to handle PostgreSQL INET type serialization correctly. This is a subtle issue many developers miss.

---

## 12. Final Assessment

The `core-banking` service has a **solid architectural foundation** that mirrors the proven patterns of `core-fraud-detection`. The code is clean, well-organized, and follows FastAPI conventions for routing, schemas, and dependency injection.

However, it lacks the **operational maturity** of its sibling service. The two critical issues (broken session lifecycle, fake readiness check) must be fixed immediately. The five high-severity issues (JWT enforcement, security headers, direct balance writes, module-level singletons, zero API tests) should be addressed before any staging deployment.

The most efficient path to improvement is to **port the hardening features from `core-fraud-detection`** — the security headers middleware, request ID middleware, rate limiter, global exception handler, JWT validator, lifespan resource management, and audit logging were all solved there and can be adapted with minimal effort.

**Rating: 6.8/10** — Clean foundation, significant hardening gaps. Estimated effort to reach 8.0+: ~25-30 hours of focused work.
