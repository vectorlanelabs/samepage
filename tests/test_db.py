from sqlalchemy import text


def test_engine_journal_mode_is_wal(engine):
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert mode == "wal"
