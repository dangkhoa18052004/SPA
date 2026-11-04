import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import text, inspect
from sqlalchemy.exc import IntegrityError
from alembic.migration import MigrationContext
from alembic.operations import Operations
from test_loyalty_migration import migration_engine


def migration(name):
    path=next(Path('migrations/versions').glob(name+'*.py'))
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_issuance_migration_preserves_reserved_used_and_guards_downgrade(migration_engine):
    engine=migration_engine
    with engine.begin() as c:
        for sql in ['CREATE TABLE khachhang (makh INTEGER PRIMARY KEY)',
            'CREATE TABLE nhanvien (manv INTEGER PRIMARY KEY)',
            'CREATE TABLE hoadon (mahd INTEGER PRIMARY KEY,tongtien NUMERIC NOT NULL)',
            'CREATE TABLE goidichvupurchase (id INTEGER PRIMARY KEY,amount NUMERIC NOT NULL)',
            'INSERT INTO khachhang VALUES (1)','INSERT INTO nhanvien VALUES (1)']:
            c.execute(text(sql))
        with Operations.context(MigrationContext.configure(c)):
            for name in ('20261003_0009','20261004_0012','20261004_0013'):migration(name).upgrade()
        c.execute(text("INSERT INTO loyalty_reward (id,name,description,reward_type,points_cost,reward_value,stock,active,minimum_spend,apply_to) VALUES (1,'Old','Old','voucher_amount',50,50000,4,true,300000,'service_invoice')"))
        for rid,status in [(1,'reserved'),(2,'used')]:
            c.execute(text("INSERT INTO loyalty_reward_redemption (id,makh,reward_id,points_spent,reward_snapshot_json,status,code,idempotency_key,target_type,target_id) VALUES (:id,1,1,50,:snapshot,:status,:code,:key,'service_invoice',:id)"),dict(id=rid,snapshot='{"name":"Old","reward_type":"voucher_amount","reward_value":"50000"}',status=status,code=f'OLD-{rid}',key=f'old-{rid}'))
        before=c.execute(text('SELECT id,status,code,reward_snapshot_json,target_id FROM loyalty_reward_redemption ORDER BY id')).all()
        new=migration('20261023_0025')
        with Operations.context(MigrationContext.configure(c)):new.upgrade()
        assert c.execute(text('SELECT id,status,code,reward_snapshot_json,target_id FROM loyalty_reward_redemption ORDER BY id')).all()==before
        assert c.execute(text('SELECT allow_points_redemption,allow_manual_gift FROM loyalty_reward')).one()==(True,False)
        assert c.execute(text("SELECT COUNT(*) FROM loyalty_reward_redemption WHERE issuance_source='points_redemption'")).scalar()==2
        assert 'uq_loyalty_target_voucher' in {i['name'] for i in inspect(c).get_indexes('loyalty_reward_redemption')}
        assert c.execute(text('SELECT COUNT(*) FROM customer_otp_registration')).scalar()==0
        # Reversible before any gifts: no hidden deletion needed to return to the old schema.
        with Operations.context(MigrationContext.configure(c)):new.downgrade();new.upgrade()
        assert c.execute(text('SELECT id,status,code,reward_snapshot_json,target_id FROM loyalty_reward_redemption ORDER BY id')).all()==before
        for source,points,once,actor,reason in [('points_redemption',0,None,None,None),('staff_gift',1,None,1,'reason'),('welcome',0,None,None,None),('staff_gift',0,None,None,'reason')]:
            with pytest.raises(IntegrityError):
                with c.begin_nested():
                    c.execute(text("INSERT INTO loyalty_reward_redemption (id,makh,reward_id,points_spent,reward_snapshot_json,status,code,idempotency_key,issuance_source,welcome_once_key,issued_by_staff,gift_reason) VALUES (10,1,1,:points,'{}','available','BAD','bad',:source,:once,:actor,:reason)"),dict(points=points,source=source,once=once,actor=actor,reason=reason))
        c.execute(text("INSERT INTO loyalty_reward_redemption (id,makh,reward_id,points_spent,reward_snapshot_json,status,code,idempotency_key,issuance_source,welcome_once_key) VALUES (3,1,1,0,'{}','available','WELCOME','welcome','welcome','welcome:1')"))
        with pytest.raises(IntegrityError):
            with c.begin_nested():
                c.execute(text("INSERT INTO loyalty_reward_redemption (id,makh,reward_id,points_spent,reward_snapshot_json,status,code,idempotency_key,issuance_source,welcome_once_key) VALUES (4,1,1,0,'{}','available','WELCOME2','welcome2','welcome','welcome:1')"))
        with Operations.context(MigrationContext.configure(c)):
            with pytest.raises(RuntimeError,match='Cannot downgrade'):new.downgrade()
        assert c.execute(text('SELECT COUNT(*) FROM loyalty_reward_redemption')).scalar()==3
