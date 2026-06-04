from app.services.metadata import MetadataCatalog, TableDefinition
from app.services.sql_safety import SqlSafetyValidator


def catalog() -> MetadataCatalog:
    return MetadataCatalog(
        version="test",
        created_at="now",
        tables=[TableDefinition(name="SALES_FACT", schema_name="APP")],
    )


def test_allows_select_and_applies_row_limit():
    result = SqlSafetyValidator(max_rows=50).validate("SELECT AMOUNT FROM APP.SALES_FACT", catalog())

    assert result.is_safe
    assert result.safe_sql is not None
    assert "ROWNUM <= 50" in result.safe_sql


def test_blocks_dml():
    result = SqlSafetyValidator(max_rows=50).validate("DELETE FROM APP.SALES_FACT", catalog())

    assert not result.is_safe
    assert result.errors


def test_blocks_unknown_table():
    result = SqlSafetyValidator(max_rows=50).validate("SELECT * FROM APP.SECRET_TABLE", catalog())

    assert not result.is_safe
    assert "not present" in result.errors[0]


def test_blocks_oracle_12c_row_limiting_syntax_for_oracle_11g():
    queries = [
        "SELECT AMOUNT FROM APP.SALES_FACT FETCH FIRST 10 ROWS ONLY",
        "SELECT AMOUNT FROM APP.SALES_FACT OFFSET 10 ROWS FETCH NEXT 10 ROWS ONLY",
        "SELECT AMOUNT FROM APP.SALES_FACT LIMIT 10",
    ]

    for query in queries:
        result = SqlSafetyValidator(max_rows=50).validate(query, catalog())

        assert not result.is_safe
        assert any("Oracle 11g" in error for error in result.errors)
