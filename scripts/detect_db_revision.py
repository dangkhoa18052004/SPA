"""Nhận diện revision Alembic của một database cũ chưa có bảng alembic_version.

Chỉ đọc schema, không thay đổi dữ liệu. Dùng:

    python scripts/detect_db_revision.py            # dùng DATABASE_URL
    python scripts/detect_db_revision.py --url sqlite:///instance/spa.db

Kết quả là lệnh cần chạy, ví dụ `flask db stamp 20261003_0009` rồi `flask db upgrade`.
"""
import argparse
import os
import sys

from sqlalchemy import create_engine, inspect

BASELINE = "f3b12dbde06b"

# (revision, kiểu dấu hiệu, bảng, cột) theo đúng thứ tự chuỗi migration.
MARKERS = [
    ("20261001_0001", "table", "payment_webhook_event", None),
    ("20261001_0002", "column", "lichhen", "ghichu"),
    ("20261001_0003", "table", "danhgia", None),
    ("20261002_0004", "table", "goidichvu", None),
    ("20261002_0005", "column", "goidichvu", "anhgoi"),
    ("20261003_0006", "column", "goidichvu", "post_care_instructions"),
    ("20261003_0007", "column", "thelieutrinhitem", "source_type"),
    ("20261003_0008", "table", "reviewreply", None),
    ("20261003_0009", "table", "loyalty_wallet", None),
    ("20261004_0010", "column", "lichhen", "booking_source"),
    ("20261004_0011", "column", "goidichvu", "customer_sale_enabled"),
    ("20261004_0012", "column", "loyalty_reward", "minimum_spend"),
    ("20261004_0013", "column", "loyalty_reward", "percentage_value"),
    ("20261005_0014", "table", "commission_entry", None),
    ("20261005_0015", "column", "loyalty_config", "tier_thresholds"),
    ("20261005_0016", "table", "ai_booking_draft", None),
]


def detect(engine):
    """Trả về (trạng thái, revision). Trạng thái: empty | managed | legacy | unknown."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "alembic_version" in tables:
        with engine.connect() as conn:
            version = conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
        return "managed", version
    if not tables:
        return "empty", None
    if "lichhen" not in tables or "khachhang" not in tables:
        return "unknown", None

    columns = {}

    def has(kind, table, column):
        if table not in tables:
            return False
        if kind == "table":
            return True
        if table not in columns:
            columns[table] = {c["name"] for c in insp.get_columns(table)}
        return column in columns[table]

    revision = BASELINE
    for rev, kind, table, column in MARKERS:
        if not has(kind, table, column):
            break
        revision = rev
    return "legacy", revision


def advice(state, revision):
    if state == "empty":
        return "Database rỗng: chạy `flask db upgrade`."
    if state == "managed":
        return f"Database đã được Alembic quản lý (revision {revision}): chạy `flask db upgrade`."
    if state == "legacy":
        return (f"Database cũ khớp schema tới revision {revision}.\n"
                f"Sao lưu trước, sau đó chạy:\n  flask db stamp {revision}\n  flask db upgrade")
    return "Không nhận diện được schema Bin Spa; dừng lại và kiểm tra thủ công."


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.url:
        parser.error("Cần --url hoặc biến môi trường DATABASE_URL")
    url = args.url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(url)
    try:
        state, revision = detect(engine)
    finally:
        engine.dispose()
    print(advice(state, revision))
    return 0 if state != "unknown" else 1


if __name__ == "__main__":
    sys.exit(main())
