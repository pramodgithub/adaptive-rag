# tests/test_schema_integrity.py
import sqlalchemy as sa
from database.session import engine


def test_all_expected_foreign_keys_exist():
    inspector = sa.inspect(engine)

    expected_fks = {
        ("documents", "active_version_id"): "document_versions",
        ("document_versions", "document_id"): "documents",
        ("chunks", "document_version_id"): "document_versions",
        ("ingestion_jobs", "document_version_id"): "document_versions",

    }

    for (table, column), ref_table in expected_fks.items():
        fks = inspector.get_foreign_keys(table)
        matching = [fk for fk in fks if column in fk["constrained_columns"]
                    and fk["referred_table"] == ref_table]
        assert matching, f"Missing FK: {table}.{column} -> {ref_table}"


def test_all_enum_columns_use_check_constraint_not_native_enum():
    inspector = sa.inspect(engine)
    # native Postgres ENUM types show up as USER-DEFINED in information_schema;
    # native_enum=False columns show up as character varying + a CHECK constraint
    with engine.connect() as conn:
        result = conn.execute(sa.text("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE data_type = 'USER-DEFINED'
        """)).fetchall()
        assert not result, f"Found native Postgres ENUM columns (should be native_enum=False): {result}"
