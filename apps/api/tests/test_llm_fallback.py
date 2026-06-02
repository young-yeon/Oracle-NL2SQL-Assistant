from app.services.llm import LLMService
from app.services.metadata import MetadataCatalog, MetricDefinition, TableDefinition


def test_fallback_metric_lookup_uses_catalog_expression():
    catalog = MetadataCatalog(
        version="test",
        created_at="now",
        tables=[TableDefinition(name="SALES_FACT", schema_name="APP")],
        metrics=[MetricDefinition(name="total_revenue", expression="SUM(AMOUNT)", table="SALES_FACT")],
    )

    result = LLMService(settings=object())._fallback_sql(
        catalog,
        [{"type": "metric", "target": "total_revenue"}],
    )

    assert result["sql"] == "SELECT SUM(AMOUNT) AS total_revenue FROM APP.SALES_FACT"
