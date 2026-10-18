"""Feature gates and complete-asset fallback; no production DB or built files needed."""
import json
import pytest
from app.ui_assets import portal_assets


@pytest.fixture()
def built_customer(app, tmp_path, monkeypatch):
    root = tmp_path / 'portal'
    (root / '.vite').mkdir(parents=True)
    for name in ('customer.js', 'shared.js', 'customer.css'):
        (root / name).write_text('/* test */', encoding='utf-8')
    (root / '.vite/manifest.json').write_text(json.dumps({
        'src/customer-main.ts': {'file': 'customer.js', 'imports': ['shared'], 'css': ['customer.css']},
        'shared': {'file': 'shared.js'},
    }), encoding='utf-8')
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    app.config['CUSTOMER_PUBLIC_UI_ENABLED'] = True
    return root


def test_customer_entry_requires_flag_and_honors_legacy(app, client, built_customer):
    response = client.get('/services')
    assert b'customer-ui ' in response.data
    assert b'/static/portal/customer.js' in response.data
    assert b'/static/portal/customer.css' in response.data
    assert b'aria-label="T' in response.data
    assert b'customer-ui ' not in client.get('/services?ui=legacy').data
    app.config['CUSTOMER_PUBLIC_UI_ENABLED'] = False
    assert b'customer-ui ' not in client.get('/services').data


@pytest.mark.parametrize('missing', ['customer.js', 'shared.js', 'customer.css', '.vite/manifest.json'])
def test_partial_build_serves_legacy_without_broken_entry(client, built_customer, missing):
    (built_customer / missing).unlink()
    response = client.get('/')
    assert response.status_code == 200
    assert b'customer-ui ' not in response.data
    assert b'/static/portal/customer.js' not in response.data


def test_missing_import_and_cyclic_manifest(app, built_customer):
    manifest_path = built_customer / '.vite/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['shared']['imports'] = ['src/customer-main.ts']
    manifest_path.write_text(json.dumps(manifest))
    with app.test_request_context('/'):
        assert portal_assets('src/customer-main.ts', require_complete=True)
        manifest['shared']['imports'] = ['missing']
        manifest_path.write_text(json.dumps(manifest))
        assert portal_assets('src/customer-main.ts', require_complete=True) is None


def test_package_pages_use_same_gate(client, built_customer):
    assert b'/static/portal/customer.js' in client.get('/packages').data
    assert b'/static/portal/customer.js' not in client.get('/packages?ui=legacy').data


def test_account_has_independent_gate_and_complete_legacy_fallback(app, client, built_customer):
    manifest_path = built_customer / '.vite/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['src/customer-account-main.tsx'] = {'file': 'account.js', 'css': ['customer.css']}
    manifest_path.write_text(json.dumps(manifest))
    (built_customer / 'account.js').write_text('/* test */')
    assert b'id="editProfileForm"' in client.get('/profile').data
    app.config['CUSTOMER_ACCOUNT_REACT_ENABLED'] = True
    html = client.get('/profile').data
    assert b'id="customer-edit-root"' in html
    assert b'id="editProfileForm"' not in html
    assert b'/static/portal/account.js' in html
    assert b'id="editProfileForm"' in client.get('/profile?ui=legacy').data
    (built_customer / 'account.js').unlink()
    html = client.get('/profile').data
    assert b'id="editProfileForm"' in html
    assert b'customer-ui ' not in html


def test_missing_lazy_account_chunk_uses_legacy(app, client, built_customer):
    path = built_customer / '.vite/manifest.json'
    manifest = json.loads(path.read_text())
    manifest['src/customer-account-main.tsx'] = {'file':'customer.js', 'dynamicImports':['panels']}
    manifest['panels'] = {'file':'panels.js'}
    path.write_text(json.dumps(manifest))
    app.config['CUSTOMER_ACCOUNT_REACT_ENABLED'] = True
    assert b'id="editProfileForm"' in client.get('/profile').data
