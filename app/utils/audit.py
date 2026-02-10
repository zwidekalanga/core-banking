"""Audit logging for privileged actions."""

from fastapi import Request

from app.auth.dependencies import CurrentUser
from app.utils.logging import get_logger

logger = get_logger("audit")


def audit_logged(action: str):
    """Dependency factory that logs privileged actions.

    Usage::

        @router.post("/customers", dependencies=[Depends(audit_logged("create_customer"))])
    """

    async def _log(request: Request, current_user: CurrentUser) -> None:
        try:
            client_ip = request.client.host if request.client else "unknown"
            request_id = getattr(request.state, "request_id", "n/a")
            logger.info(
                "AUDIT action=%s user=%s role=%s ip=%s request_id=%s path=%s",
                action,
                current_user.username,
                current_user.role,
                client_ip,
                request_id,
                request.url.path,
            )
        except Exception:
            logger.warning("Failed to write audit log for action=%s", action, exc_info=True)

    return _log
