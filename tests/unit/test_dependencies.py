"""Unit tests for dependency injection utilities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.dependencies import get_db_session


def _make_mock_request():
    """Create a mock request with a session factory on app.state."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    class _ContextManager:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            pass

    factory = MagicMock()
    factory.return_value = _ContextManager()

    request = MagicMock()
    request.app.state.session_factory = factory

    return request, session


@pytest.mark.asyncio
class TestGetDbSession:
    async def test_commits_on_success(self):
        """Session should be committed when the request handler succeeds."""
        request, session = _make_mock_request()

        gen = get_db_session(request)
        yielded_session = await gen.__anext__()

        assert yielded_session is session

        # Simulate successful completion
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        session.close.assert_awaited_once()

    async def test_rolls_back_on_exception(self):
        """Session should be rolled back when the request handler raises."""
        request, session = _make_mock_request()

        gen = get_db_session(request)
        await gen.__anext__()

        # Simulate an exception during the request
        with pytest.raises(ValueError):
            await gen.athrow(ValueError("test error"))

        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()
        session.close.assert_awaited_once()
