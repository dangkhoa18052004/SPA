"""Public category source-of-truth and opt-in pagination compatibility."""
from decimal import Decimal
import pytest
from app.extensions import db
from app.models import DichVu, DanhMucDichVu

@pytest.fixture
def public_catalog(app):
    with app.app_context():
        categories = [DanhMucDichVu(name=n, slug=s, active=a) for n,s,a in
            [('Da mặt','facial',True),('Da mụn','acne',True),('Trống','empty',True),('Ẩn','hidden',False)]]
        db.session.add_all(categories); db.session.flush()
        for i in range(25):
            db.session.add(DichVu(tendv=f'Massage {i:02d}', mota='Dữ liệu 100% _ \\', gia=100000+i*10000,
                thoiluong=30+i, active=True, category_id=categories[i%2].id if i<24 else None))
        db.session.add_all([DichVu(tendv='Hidden metadata', gia=1, category_id=categories[3].id, active=True),
            DichVu(tendv='Inactive service', gia=1, category_id=categories[0].id, active=False)])
        db.session.commit()

def test_public_categories_counts_and_no_phantoms(client, public_catalog):
    response = client.get('/api/services/categories')
    assert response.status_code == 200
    rows = response.json['categories']
    assert {c['slug']:c['service_count'] for c in rows} == {'facial':12,'acne':12}
    assert all(set(c)=={'id','name','slug','service_count'} for c in rows)
    assert 'no-store' in response.headers['Cache-Control']

def test_exact_category_and_neutral_unassigned(client, public_catalog):
    rows = client.get('/api/services?category=facial').json['services']
    assert len(rows)==12 and {r['category_slug'] for r in rows}=={'facial'}
    assert not client.get('/api/services?category=hidden').json['services']
    rows = client.get('/api/services').json['services']
    assert len(rows)==26
    assert all(r['category_name'] is None for r in rows if r['category_slug'] is None)
    assert not any(r['category_slug']=='hidden' for r in rows)

def test_paging_after_rank_and_backward_compatibility(client, public_catalog, customer_auth_headers):
    for headers in ({},customer_auth_headers):
        full = client.get('/api/services',headers=headers).json
        assert 'page' not in full and len(full['services'])==26
        pages=[client.get(f'/api/services?page={p}',headers=headers).json for p in (1,2,3)]
        assert [len(p['services']) for p in pages]==[9,9,8]
        assert all(p['total']==26 and p['total_pages']==3 and p['per_page']==9 for p in pages)
        assert [r['madv'] for p in pages for r in p['services']]==[r['madv'] for r in full['services']]
    assert client.get('/api/services?page=999').json['services']==[]
    assert client.get('/api/services?per_page=10000').json['per_page']==100

@pytest.mark.parametrize('query',['page=0','page=nan','per_page=0','min_price=-1','max_price=NaN',
    'min_price=Infinity','min_duration=oops','min_price=10&max_price=1','min_duration=31&max_duration=30'])
def test_invalid_filter_returns_400(client, public_catalog, query):
    assert client.get('/api/services?'+query).status_code==400

def test_ranges_search_and_stable_sort(client, public_catalog):
    result=client.get('/api/services?min_price=120000&max_price=200000&min_duration=33&max_duration=36&sort=price-desc&page=1').json
    assert [Decimal(r['gia']) for r in result['services']]==[Decimal(v) for v in (160000,150000,140000,130000)]
    assert client.get('/api/services?search=%25').json['total']==25
    assert client.get('/api/services?search=_').json['total']==25
    assert client.get('/api/services?search=NO_MATCH&page=1').json['total_pages']==0

def test_empty_categories(client):
    assert client.get('/api/services/categories').json['categories']==[]

@pytest.mark.parametrize('size',[0,1,9,10,25,100,500])
def test_catalog_cardinality_and_all_page_boundaries(app,client,size):
    with app.app_context():
        db.session.add_all([DichVu(tendv=f'Service {i:04d}',gia=100,thoiluong=30,active=True) for i in range(size)])
        db.session.commit()
    full=client.get('/api/services?sort=name-asc').json
    assert full['total']==size and len(full['services'])==size
    seen=[]
    for page in range(1,(size+8)//9+2):
        result=client.get(f'/api/services?sort=name-asc&page={page}').json
        assert result['total']==size and len(result['services'])<=9
        assert result['total_pages']==(size+8)//9
        seen.extend(r['madv'] for r in result['services'])
    assert seen==[r['madv'] for r in full['services']]

def test_paged_images_are_loaded_in_one_bounded_read(app,client):
    from sqlalchemy import event
    import base64
    with app.app_context():
        db.session.add_all([DichVu(tendv=f'Image {i}',gia=100,active=True,anhdichvu=b'fixture-image') for i in range(25)])
        db.session.commit();db.session.remove()
        statements=[]
        def capture(conn,cursor,statement,parameters,context,executemany):
            if 'dichvu.anhdichvu' in statement.lower():statements.append(statement)
        event.listen(db.engine,'before_cursor_execute',capture)
        try:
            result=client.get('/api/services?page=2&sort=name-asc').json
        finally:
            event.remove(db.engine,'before_cursor_execute',capture)
    assert len(result['services'])==9 and result['total']==25
    assert all(r['anhdichvu']==base64.b64encode(b'fixture-image').decode() for r in result['services'])
    assert len(statements)==1 and ' IN (' in statements[0]
