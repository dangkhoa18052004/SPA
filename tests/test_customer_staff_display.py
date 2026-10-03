"""Exercise actual booking JS rendering with a small DOM and API stub."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_customer_staff_states_and_empty_selection():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the booking UI regression test")
    script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
const source = fs.readFileSync(process.argv[1], 'utf8');
const functions = source.slice(source.indexOf('function getStaffAvailabilityBadge('), source.indexOf('function selectStaff('));
const container = {innerHTML: ''};
const elements = {appointmentDate: {value:'2026-10-05'}, appointmentTime: {value:'09:00'}, staffSelection:container};
let responseStaff = [], summaries = 0;
const context = vm.createContext({
    document: {getElementById: id=>elements[id]},
    console,
    getAuthHeaders:()=>({}),
    customerAuthFetch:async (url, options)=>{
        assert.equal(url, '/api/appointments/available-staff');
        assert.deepEqual(JSON.parse(options.body), {ngaygio:'2026-10-05T09:00',madv_list:[1]});
        return {ok:true,json:async()=>({success:true,staff:responseStaff})};
    },
    updateSummary:()=>summaries++,
});
vm.runInContext('let selectedServices=[1]; let selectedStaff=1;'+functions,context);
(async()=>{
    responseStaff = [
        {manv:1, hoten:'Free Technician', available:true, reason:'available'},
        {manv:2, hoten:'Busy Technician', available:false, reason:'appointment_conflict'},
        {manv:3, hoten:'No Shift', available:false, reason:'not_working'},
        {manv:4, hoten:'Inactive Technician', available:false, reason:'inactive'},
    ];
    await context.loadAvailableStaff();
    assert.equal((container.innerHTML.match(/data-staff-id=/g)||[]).length,2);
    assert.match(container.innerHTML,/Còn trống/);
    assert.match(container.innerHTML,/Đã có lịch/);
    assert.match(container.innerHTML,/selectStaff\(1,/);
    assert.doesNotMatch(container.innerHTML,/selectStaff\(2,|No Shift|Không có ca làm|Inactive Technician/);
    assert.equal(vm.runInContext('selectedStaff',context),1);

    // A previously selected technician becoming busy must be deselected.
    responseStaff = [{manv:1,hoten:'Busy Technician',available:false,reason:'appointment_conflict'}];
    await context.loadAvailableStaff();
    assert.equal(vm.runInContext('selectedStaff',context),null);
    assert.match(container.innerHTML,/Đã có lịch/);
    assert.doesNotMatch(container.innerHTML,/Không có kỹ thuật viên/);

    for (const staff of [[], [{manv:1,hoten:'No Shift',available:false,reason:'not_working'}]]) {
        vm.runInContext('selectedStaff=1',context);
        responseStaff=staff;
        await context.loadAvailableStaff();
        assert.match(container.innerHTML,/Không có kỹ thuật viên nào làm việc trong khung giờ này/);
        assert.doesNotMatch(container.innerHTML,/data-staff-id=/);
        assert.equal(vm.runInContext('selectedStaff',context),null);
    }
    assert.equal(summaries,3);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(
        [node, "-e", script, str(Path("app/static/js/customers/appointments.js").resolve())],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
