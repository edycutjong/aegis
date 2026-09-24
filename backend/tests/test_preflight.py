"""Tests for app.preflight — dependency health checks (all I/O mocked)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import preflight


def _db(results):
    db = MagicMock()
    db.execute_sql = AsyncMock(side_effect=results)
    return db


@pytest.mark.asyncio
async def test_check_model_ok(mock_settings):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content=" ok "))
    with patch("app.preflight._create_model", return_value=llm):
        assert await preflight._check_model("gpt-4.1") == (True, "ok")


@pytest.mark.asyncio
async def test_check_model_non_string_content(mock_settings):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content=[{"text": "ok"}]))
    with patch("app.preflight._create_model", return_value=llm):
        ok, _ = await preflight._check_model("gemini-2.5-flash")
    assert ok


@pytest.mark.asyncio
async def test_check_tables_ok_and_failure():
    ok_rows = [{"success": True, "data": [{"n": 5}]}] * 4
    with patch("app.preflight.get_supabase", return_value=_db(ok_rows)):
        ok, detail = await preflight._check_tables()
    assert ok and "customers=5" in detail

    with patch("app.preflight.get_supabase", return_value=_db([{"success": False, "error": "suspended"}])):
        ok, detail = await preflight._check_tables()
    assert not ok and "suspended" in detail


@pytest.mark.asyncio
async def test_privilege_boundary():
    denied = {"success": False, "error": "permission denied for schema auth"}
    with patch("app.preflight.get_supabase", return_value=_db([denied])):
        assert (await preflight._check_privilege_boundary())[0] is True
    with patch("app.preflight.get_supabase", return_value=_db([{"success": True, "data": [{"count": 3}]}])):
        ok, detail = await preflight._check_privilege_boundary()
    assert not ok and "broken" in detail


def test_is_throttle():
    assert preflight._is_throttle(Exception("Error code: 429"))
    assert preflight._is_throttle(type("ResourceExhausted", (Exception,), {})("quota"))
    assert not preflight._is_throttle(Exception("404 model does not exist"))


@pytest.mark.asyncio
async def test_main_reports_failures_and_throttles(mock_settings, capsys):
    async def model_check(name):
        if name == "gemini-2.5-flash":
            raise Exception("429 quota")
        if name == "gpt-4.1":
            raise Exception("404 model not found")
        return True, "ok"

    with patch("app.preflight._check_model", side_effect=model_check), \
         patch("app.preflight._check_tables", AsyncMock(return_value=(True, "customers=51"))), \
         patch("app.preflight._check_privilege_boundary", AsyncMock(return_value=(True, "denied"))):
        code = await preflight.main()

    out = capsys.readouterr().out
    assert code == 1
    assert "throttled right now" in out
    assert "404 model not found" in out
    assert "1 check(s) failed" in out


@pytest.mark.asyncio
async def test_main_all_healthy(mock_settings, capsys):
    with patch("app.preflight._check_model", AsyncMock(return_value=(True, "ok"))), \
         patch("app.preflight._check_tables", AsyncMock(return_value=(True, "x"))), \
         patch("app.preflight._check_privilege_boundary", AsyncMock(return_value=(True, "denied"))):
        assert await preflight.main() == 0
    assert "all dependencies healthy" in capsys.readouterr().out
