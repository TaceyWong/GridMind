import pytest

from gridmind.core.errors import GridMindError
from gridmind.nl2sql.sql_guard import validate_sql


def test_select_ok():
    sql = validate_sql("SELECT device_id, name FROM devices LIMIT 10")
    assert "devices" in sql.lower()


def test_reject_delete():
    with pytest.raises(GridMindError):
        validate_sql("DELETE FROM devices")


def test_reject_unknown_table():
    with pytest.raises(GridMindError):
        validate_sql("SELECT * FROM secrets")
