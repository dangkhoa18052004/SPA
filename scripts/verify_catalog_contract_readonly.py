"""Verify public catalog against configured DB, enforcing READ ONLY per request.

No login, migrations, seed, transaction mutations, email or provider requests.
Only aggregate counts are printed, never URLs, tokens, images or customer data.
"""
import json
import logging
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from app import create_app
from app.extensions import db
from app.models import DanhMucDichVu, DichVu

def main():
    logging.disable(logging.CRITICAL)
    try:
        app=create_app(dict(TESTING=True,APP_ENV='testing',RENDER=False,
            STAFF_SECURITY_ENABLED=False,AUTH_RATE_LIMIT_ENABLED=False,OBSERVABILITY_ENABLED=False,
            RECOMMENDATION_METRICS_ENABLED=False,SEPAY_POLL_ENABLED=False,GEMINI_API_KEY='',
            MAIL_SUPPRESS_SEND=True))
        def readonly():
            db.session.execute(text('SET TRANSACTION READ ONLY' if db.engine.dialect.name=='postgresql' else 'PRAGMA query_only=ON'))
        app.before_request(readonly)
        with app.app_context():
            readonly()
            total=DichVu.query.filter_by(active=True).count()
            categories={c.id:c.slug for c in DanhMucDichVu.query.filter_by(active=True) if DichVu.query.filter_by(active=True,category_id=c.id).count()}
            db.session.rollback()
        client=app.test_client()
        category_response=client.get('/api/services/categories')
        assert category_response.status_code==200
        assert {c['id']:c['slug'] for c in category_response.json['categories']}==categories
        result=client.get('/api/services?page=1&per_page=9&sort=name-asc')
        assert result.status_code==200 and result.json['total']==total
        assert len(result.json['services'])==min(9,total) and result.json['total_pages']==(total+8)//9
        print(json.dumps(dict(result='PASS',mode='database-enforced-read-only',active_services=total,
            public_categories=len(categories),first_page=len(result.json['services']),total_pages=result.json['total_pages'])))
        return 0
    except Exception as error:
        print(json.dumps(dict(result='FAIL',error_type=type(error).__name__)))
        return 1

if __name__=='__main__':
    raise SystemExit(main())
