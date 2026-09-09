import pytest
pytestmark = pytest.mark.asyncio
import asyncio
from unittest.mock import AsyncMock, patch
from src.config.database import with_db_retry, is_transient_error


class TestIsTransientError:
    def test_deadlock_detected(self):
        assert is_transient_error(Exception("deadlock detected")) is True

    def test_could_not_obtain_lock(self):
        assert is_transient_error(Exception("could not obtain lock")) is True

    def test_connection_reset(self):
        assert is_transient_error(Exception("connection reset")) is True

    def test_connection_refused(self):
        assert is_transient_error(Exception("connection refused")) is True

    def test_server_closed_connection(self):
        assert is_transient_error(Exception("server closed the connection")) is True

    def test_connection_timed_out(self):
        assert is_transient_error(Exception("connection timed out")) is True

    def test_too_many_connections(self):
        assert is_transient_error(Exception("too many connections")) is True

    def test_sorry_too_many_clients(self):
        assert is_transient_error(Exception("sorry, too many clients")) is True

    def test_non_transient_error(self):
        assert is_transient_error(Exception("syntax error")) is False

    def test_empty_message(self):
        assert is_transient_error(Exception("")) is False


class TestWithDbRetry:
    async def test_succeeds_on_first_attempt(self):
        @with_db_retry(max_retries=3, base_delay=0.01, max_delay=0.1)
        async def success():
            return "ok"

        result = await success()
        assert result == "ok"

    async def test_retries_on_transient_error(self):
        call_count = 0

        @with_db_retry(max_retries=3, base_delay=0.01, max_delay=0.1)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("deadlock detected")
            return "ok"

        result = await flaky()
        assert result == "ok"
        assert call_count == 3

    async def test_raises_after_max_retries(self):
        @with_db_retry(max_retries=2, base_delay=0.01, max_delay=0.05)
        async def always_fails():
            raise Exception("deadlock detected")

        with pytest.raises(Exception, match="deadlock detected"):
            await always_fails()

    async def test_raises_non_transient_immediately(self):
        call_count = 0

        @with_db_retry(max_retries=3, base_delay=0.01, max_delay=0.1)
        async def non_transient():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad input")

        with pytest.raises(ValueError, match="bad input"):
            await non_transient()
        assert call_count == 1

    async def test_passes_args_and_kwargs(self):
        @with_db_retry(max_retries=1, base_delay=0.01, max_delay=0.05)
        async def add(a, b, c=0):
            return a + b + c

        result = await add(1, 2, c=3)
        assert result == 6
