import shutil
import subprocess
from pathlib import Path

import pytest

from app.extensions import db
from app.models import DichVu


def test_empty_packages_and_treatments_are_json(client, customer_auth_headers):
    for url, key, headers in [
        ('/api/packages', 'packages', {}),
        ('/api/packages/my-treatments', 'treatments', customer_auth_headers),
    ]:
        response = client.get(url, headers=headers)
        assert response.status_code == 200
        assert response.mimetype == 'application/json'
        assert response.json == {'success': True, key: []}
    response = client.get('/api/packages/my-treatments')
    assert response.status_code == 401
    assert response.mimetype == 'application/json'
    assert response.json['success'] is False
    assert 'Location' not in response.headers


def test_services_empty_active_list_is_json(app, client):
    with app.app_context():
        DichVu.query.update({'active': False})
        db.session.commit()
    response = client.get('/api/services')
    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert response.json['services'] == []
    assert response.json['success'] is True


@pytest.mark.parametrize('response_kind', ['html', 'invalid-json'])
def test_package_ui_handles_non_json_without_raw_parser_error(response_kind):
    node = shutil.which('node')
    assert node, 'Node is required to verify the JavaScript response handling'
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const list={textContent:''};
let calls=0;
const response={ok:false,status:500,headers:{get:()=>process.argv[1]==='html'?'text/html':'application/json'},
 json:async()=>{throw new SyntaxError("Unexpected token '<'");}};
const context={console:{error:()=>{}},Intl,Date,Map,window:{CustomerAuth:{fetch:async()=>{calls++;return response;}}},
 document:{querySelector:()=>null,getElementById:id=>id==='myTreatments'?list:null,addEventListener:()=>{}}};
vm.runInNewContext(fs.readFileSync('app/static/js/packages.js','utf8'),context);
context.window.PackageCare.loadTreatments().then(()=>{
 assert.equal(calls,1);
 assert(list.textContent.length>0);
 assert(!list.textContent.includes('Unexpected token'));
 assert(!list.textContent.includes('<'));
});
'''
    subprocess.run([node, '-e', script, response_kind], check=True,
                   cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
