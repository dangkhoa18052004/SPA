"""SELECT-only category audit; outputs counts, never database URL or PII."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from app.config import Config

def main():
    try:
        engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, connect_args={'connect_timeout': 10})
        with engine.connect() as connection, connection.begin():
            if engine.dialect.name == 'postgresql':
                connection.execute(text('SET TRANSACTION READ ONLY'))
            counts = {
                'categories': 'SELECT COUNT(*) FROM danhmucdichvu',
                'active_categories': 'SELECT COUNT(*) FROM danhmucdichvu WHERE active = true',
                'active_services': 'SELECT COUNT(*) FROM dichvu WHERE active = true',
                'uncategorized_active': 'SELECT COUNT(*) FROM dichvu WHERE active = true AND category_id IS NULL',
                'invalid_category': 'SELECT COUNT(*) FROM dichvu s LEFT JOIN danhmucdichvu c ON c.id=s.category_id WHERE s.category_id IS NOT NULL AND c.id IS NULL',
                'missing_images': "SELECT COUNT(*) FROM dichvu WHERE active = true AND (anhdichvu IS NULL OR anhdichvu = '')",
                'duplicate_slugs': 'SELECT COUNT(*) FROM (SELECT slug FROM danhmucdichvu GROUP BY slug HAVING COUNT(*)>1) d',
            }
            result = {key:connection.execute(text(sql)).scalar() for key,sql in counts.items()}
            result['category_counts'] = [dict(row) for row in connection.execute(text('SELECT c.id,c.name,c.slug,c.active,COUNT(s.madv) AS service_count FROM danhmucdichvu c LEFT JOIN dichvu s ON s.category_id=c.id AND s.active=true GROUP BY c.id,c.name,c.slug,c.active ORDER BY c.name,c.id')).mappings()]
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        # Exception strings may contain credentials/host details.
        print(json.dumps({'audit':'unavailable','error_type':type(error).__name__}))
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
