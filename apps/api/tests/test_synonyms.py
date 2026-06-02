from app.services.metadata import ColumnDefinition, MetadataCatalog, TableDefinition, TermDefinition
from app.services.synonyms import SynonymResolver


def test_resolves_terms_tables_and_columns():
    catalog = MetadataCatalog(
        version="test",
        created_at="now",
        tables=[TableDefinition(name="SALES_FACT", display_name="Sales", synonyms=["revenue"])],
        columns=[ColumnDefinition(table="SALES_FACT", name="AMOUNT", display_name="Amount", synonyms=["total"])],
        terms=[TermDefinition(term="last month", canonical_type="filter", canonical_value="previous_month")],
    )

    matches = SynonymResolver().resolve("show revenue total for last month", catalog)

    assert {match["type"] for match in matches} >= {"table", "column", "filter"}

