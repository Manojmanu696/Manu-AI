"""Small, ordered SQLite migrations for the single-user local database.

Migrations are additive: existing library, memories, backups, and demo markers
are left in place. `create_all` still creates new tables, while this runner
adds columns to tables created by earlier Manu AI versions.
"""
from sqlalchemy import Engine, inspect, text


def migrate(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        ))
        applied = {row[0] for row in connection.execute(text("SELECT version FROM schema_migrations"))}
        if 1 not in applied:
            inspector = inspect(connection)
            additions = {
                "catalogue_items": {
                    "source_provider": "VARCHAR(40) NOT NULL DEFAULT 'local'",
                    "provider_id": "VARCHAR(120)",
                    "backdrop_url": "VARCHAR(1000) NOT NULL DEFAULT ''",
                    "original_language": "VARCHAR(12) NOT NULL DEFAULT ''",
                    "vote_count": "INTEGER NOT NULL DEFAULT 0",
                    "popularity": "FLOAT",
                    "trailer_url": "VARCHAR(1000) NOT NULL DEFAULT ''",
                    "watch_url": "VARCHAR(1000) NOT NULL DEFAULT ''",
                    "watch_providers_json": "TEXT NOT NULL DEFAULT '[]'",
                    "credits_json": "TEXT NOT NULL DEFAULT '{}'",
                    "genre_ids_json": "TEXT NOT NULL DEFAULT '[]'",
                    "series_status": "VARCHAR(40) NOT NULL DEFAULT ''",
                    "runtime_minutes": "INTEGER",
                    "original_title": "VARCHAR(300) NOT NULL DEFAULT ''",
                },
                "recommendation_feedback": {
                    "reason": "VARCHAR(40) NOT NULL DEFAULT ''",
                    "context": "VARCHAR(80) NOT NULL DEFAULT ''",
                    "rating": "INTEGER",
                    "undone": "BOOLEAN NOT NULL DEFAULT 0",
                },
            }
            for table, columns in additions.items():
                existing = {col["name"] for col in inspector.get_columns(table)}
                for name, declaration in columns.items():
                    if name not in existing:
                        connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}'))
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_catalogue_provider_id "
                "ON catalogue_items(source_provider, provider_id) WHERE provider_id IS NOT NULL"
            ))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_catalogue_source_provider ON catalogue_items(source_provider)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_discovery_cache_expires ON discovery_section_cache(expires_at)"))
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (1)"))
            applied.add(1)
        if 2 not in applied:
            existing = {col["name"] for col in inspect(connection).get_columns("catalogue_items")}
            if "details_fetched_at" not in existing:
                connection.execute(text("ALTER TABLE catalogue_items ADD COLUMN details_fetched_at DATETIME"))
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (2)"))
            applied.add(2)
        if 3 not in applied:
            connection.execute(text("CREATE TABLE IF NOT EXISTS app_settings (key VARCHAR(80) PRIMARY KEY, value TEXT NOT NULL)"))
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (3)"))
            applied.add(3)
        if 4 not in applied:
            existing = {col["name"] for col in inspect(connection).get_columns("recommendation_feedback")}
            additions = {
                "library_item_id": "INTEGER",
                "library_item_created": "BOOLEAN NOT NULL DEFAULT 0",
                "previous_library_state_json": "TEXT NOT NULL DEFAULT '{}'",
            }
            for name, declaration in additions.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE "recommendation_feedback" ADD COLUMN "{name}" {declaration}'))
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (4)"))
            applied.add(4)
        if 5 not in applied:
            existing = {col["name"] for col in inspect(connection).get_columns("catalogue_items")}
            additions = {"similar_catalogue_ids_json": "TEXT NOT NULL DEFAULT '[]'",
                         "episode_details_json": "TEXT NOT NULL DEFAULT '[]'",
                         "schedule_json": "TEXT NOT NULL DEFAULT '{}'"}
            for name, declaration in additions.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE "catalogue_items" ADD COLUMN "{name}" {declaration}'))
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (5)"))
            applied.add(5)
        if 6 not in applied:
            existing = {col["name"] for col in inspect(connection).get_columns("recommendation_feedback")}
            if "taste_signal_id" not in existing:
                connection.execute(text("ALTER TABLE recommendation_feedback ADD COLUMN taste_signal_id INTEGER"))
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (6)"))
            applied.add(6)
        if 7 not in applied:
            connection.execute(text(
                "CREATE TABLE IF NOT EXISTS taste_embeddings ("
                "id INTEGER PRIMARY KEY, entity_key VARCHAR(200) NOT NULL UNIQUE, content_hash VARCHAR(64) NOT NULL, "
                "model_name VARCHAR(120) NOT NULL DEFAULT '', vector_json TEXT NOT NULL, updated_at DATETIME NOT NULL)"
            ))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_taste_embeddings_entity_key ON taste_embeddings(entity_key)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_taste_embeddings_content_hash ON taste_embeddings(content_hash)"))
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (7)"))
            applied.add(7)
        if 8 not in applied:
            existing = {col["name"] for col in inspect(connection).get_columns("catalogue_items")}
            if "countries_json" not in existing:
                connection.execute(text("ALTER TABLE catalogue_items ADD COLUMN countries_json TEXT NOT NULL DEFAULT '[]'"))
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES (8)"))
