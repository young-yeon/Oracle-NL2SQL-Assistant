# Metadata Workbook Format

The importer accepts an Excel workbook with the following sheets. Header names are normalized, so common variants such as `table_name`, `Table Name`, and `table` are accepted.

## tables

| column | required | description |
| --- | --- | --- |
| name | yes | Physical table name |
| schema | no | Oracle schema or owner |
| display_name | no | Business-facing table name |
| description | no | Business description |
| synonyms | no | Comma, semicolon, or pipe separated aliases |

## columns

| column | required | description |
| --- | --- | --- |
| table | yes | Physical table name |
| name | yes | Physical column name |
| data_type | no | Oracle data type |
| display_name | no | Business-facing column name |
| description | no | Business description |
| synonyms | no | Comma, semicolon, or pipe separated aliases |
| semantic_type | no | Optional type such as date, amount, code, dimension |
| nullable | no | yes/no |

## relationships

| column | required | description |
| --- | --- | --- |
| left_table | yes | Source table |
| left_column | yes | Source column |
| right_table | yes | Target table |
| right_column | yes | Target column |
| join_type | no | inner, left, right |
| description | no | Relationship notes |

## terms

| column | required | description |
| --- | --- | --- |
| term | yes | User-facing business term |
| canonical_type | no | table, column, metric, filter, concept |
| canonical_value | no | Target name or expression |
| synonyms | no | Comma, semicolon, or pipe separated aliases |
| description | no | Meaning and usage |

## metrics

| column | required | description |
| --- | --- | --- |
| name | yes | Metric name |
| expression | yes | SQL expression, for example `SUM(AMOUNT)` |
| table | no | Default fact table |
| grain | no | Metric grain |
| synonyms | no | Comma, semicolon, or pipe separated aliases |
| description | no | Meaning and usage |

