import React, { useEffect, useRef, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { Alert, App, Button, ConfigProvider, Descriptions, Drawer, Empty, Form, Input, Select, Space, Table, Tag } from 'antd';
import viVN from 'antd/locale/vi_VN';
import { customerApi } from './api';
import { customerTheme } from './theme';
import { price } from './catalog';

export type Profile = {hoten: string; sdt: string; diachi: string; email: string};
type Invoice = {mahd: number; ngaylap: string; tongtien: string; payable_amount?: string; original_total?: string; reward_discount?: string; loyalty_discount?: string; trangthai: string; chitiet?: {tendv: string; soluong: number; dongia: string; thanhtien: string}[]};
type Appointment = {malh: number; ngaygio: string; dichvu: string; nhanvien?: string; ghichu?: string; trangthai: string; trangthai_vi?: string; can_cancel: boolean; can_change_services: boolean; can_review?: boolean; invoice?: Invoice; review?: unknown};
export type Bridge = {setProfile: (p: Profile) => void; showSection: (section: string) => void; appointments: (rows: Appointment[]) => void; invoices: (rows: Invoice[]) => void; error: (section: 'appointments'|'invoices', message: string) => void};
declare global {
  interface Window {
    CustomerAccount?: Bridge;
    loadUserProfile: () => Promise<void>;
    loadUserAppointments: () => Promise<void>;
    loadUserInvoices: () => Promise<void>;
    switchSection: (name: string) => void;
    cancelAppointment: (id: number, confirmed?: boolean) => Promise<void>;
    openChangeServices: (id: number) => Promise<void>;
    openReviewModal: (id: number) => void;
  }
}
const roots = new Map<string, Root>();
const theme = customerTheme();
let profile: Profile | undefined;
function render(id: string, content: React.ReactNode, list = false) {
  const node = document.getElementById(id);
  if (!node) return;
  let root = roots.get(id);
  if (!root) { root = createRoot(node); roots.set(id, root); }
  const app = <ConfigProvider theme={theme} locale={viVN}><App>{content}</App></ConfigProvider>;
  root.render(list ? <li className="customer-react-list-item">{app}</li> : app);
}
function EditProfile({user}: {user: Profile}) {
  const [form] = Form.useForm();
  const [status, setStatus] = useState<{type:'success'|'error'; text:string}>();
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  useEffect(() => { form.setFieldsValue(user); }, [form, user]);
  return <Form form={form} layout="vertical" onFinish={async values => {
    if (lock.current) return;
    lock.current = true; setBusy(true); setStatus(undefined);
    try {
      await customerApi('/api/profile/update', {method:'PUT',body:JSON.stringify(values)});
      await window.loadUserProfile(); setStatus({type:'success',text:'Đã lưu thông tin của bạn.'});
    } catch (error) { setStatus({type:'error',text:(error as Error).message}); }
    finally {lock.current=false;setBusy(false);}
  }}>
    {status && <Alert type={status.type} message={status.text} showIcon role="status" />}
    <Form.Item label="Họ và tên" name="hoten" rules={[{required:true,message:'Vui lòng nhập họ và tên.'}]}><Input autoComplete="name" /></Form.Item>
    <Form.Item label="Số điện thoại" name="sdt"><Input type="tel" autoComplete="tel" /></Form.Item>
    <Form.Item label="Địa chỉ" name="diachi"><Input autoComplete="street-address" /></Form.Item>
    <Space wrap><Button type="primary" htmlType="submit" loading={busy}>Lưu thay đổi</Button><Button disabled={busy} onClick={()=>window.switchSection('info')}>Quay lại tài khoản</Button></Space>
  </Form>;
}
function PasswordForm() {
  const [form] = Form.useForm();
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [status,setStatus] = useState<{type:'success'|'error';text:string}>();
  return <Form form={form} layout="vertical" onFinish={async values=>{
    if(lock.current)return;lock.current=true;setBusy(true);setStatus(undefined);
    try {
      // A wrong current password is a business 401, not an expired JWT.
      const response=await window.CustomerAuth.fetch('/api/profile/change-password',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({matkhau_cu:values.old,matkhau_moi:values.password})});
      const result=await response.json();
      if(!response.ok||!result.success)throw new Error(result.message||result.msg||'Chưa đổi được mật khẩu.');
      form.resetFields();setStatus({type:'success',text:'Đã đổi mật khẩu.'});
    }catch(error){setStatus({type:'error',text:(error as Error).message});}
    finally{lock.current=false;setBusy(false);}
  }}>
    {status&&<Alert type={status.type} message={status.text} showIcon role="status"/>}
    <Form.Item name="old" label="Mật khẩu hiện tại" rules={[{required:true,message:'Vui lòng nhập mật khẩu hiện tại.'}]}><Input.Password autoComplete="current-password"/></Form.Item>
    <Form.Item name="password" label="Mật khẩu mới" rules={[{required:true,message:'Vui lòng nhập mật khẩu mới.'}]}><Input.Password autoComplete="new-password"/></Form.Item>
    <Form.Item name="confirm" label="Nhập lại mật khẩu mới" dependencies={['password']} rules={[{required:true,message:'Vui lòng nhập lại mật khẩu.'},({getFieldValue})=>({validator:(_,v)=>v===getFieldValue('password')?Promise.resolve():Promise.reject(new Error('Mật khẩu chưa khớp.'))})]}><Input.Password autoComplete="new-password"/></Form.Item>
    <Button type="primary" htmlType="submit" loading={busy}>Đổi mật khẩu</Button>
  </Form>;
}
function useMobile() {
  const [mobile,setMobile]=useState(()=>matchMedia('(max-width:767px)').matches);
  useEffect(()=>{const media=matchMedia('(max-width:767px)');const update=()=>setMobile(media.matches);media.addEventListener('change',update);return()=>media.removeEventListener('change',update);},[]);
  return mobile;
}
const appointmentLabels: Record<string,string>={pending:'Chờ xác nhận',confirmed:'Đã xác nhận',in_progress:'Đang thực hiện',completed:'Đã hoàn thành',cancelled:'Đã hủy'};
const date=(value:string)=>new Date(value).toLocaleString('vi-VN');
function Appointments({rows}:{rows:Appointment[]}) {
  const [filter,setFilter]=useState('all');
  const [error,setError]=useState('');
  const [detail,setDetail]=useState<Appointment>();
  const {modal}=App.useApp();
  const mobile=useMobile();
  const visible=rows.filter(row=>filter==='all'||row.trangthai===filter);
  const status=(row:Appointment)=><Tag>{row.trangthai_vi||appointmentLabels[row.trangthai]||'Không xác định'}</Tag>;
  const actions=(row:Appointment)=><Space wrap>
    <Button onClick={()=>setDetail(row)}>Chi tiết</Button>
    {row.can_change_services&&<Button onClick={()=>window.openChangeServices(row.malh)}>Đổi dịch vụ</Button>}
    {row.invoice?.trangthai==='Chưa thanh toán'&&['pending','confirmed'].includes(row.trangthai)&&<Button onClick={()=>{setError('');void window.LoyaltyPayment.openCustomerInvoice(row.invoice!.mahd).catch(e=>setError(e.message));}}>Thanh toán</Button>}
    {row.trangthai==='completed'&&<Button onClick={()=>window.openReviewModal(row.malh)}>Đánh giá</Button>}
    {row.can_cancel&&<Button danger onClick={()=>modal.confirm({title:'Hủy lịch hẹn này?',content:'Spa sẽ cập nhật lịch hẹn và hoàn lượt gói đang giữ theo điều kiện của lịch.',okText:'Hủy lịch',cancelText:'Giữ lịch',okButtonProps:{danger:true},onOk:()=>window.cancelAppointment(row.malh,true)})}>Hủy lịch</Button>}
  </Space>;
  return <>
    <Space className="customer-account-toolbar" wrap><label htmlFor="appointment-filter">Trạng thái</label><Select id="appointment-filter" value={filter} onChange={setFilter} options={[{value:'all',label:'Tất cả'},...Object.entries(appointmentLabels).map(([value,label])=>({value,label}))]}/><Button onClick={()=>window.loadUserAppointments()}>Tải lại</Button></Space>
    {error&&<Alert type="error" message={error} role="alert"/>}
    {mobile?<div className="customer-account-cards">{visible.length?visible.map(row=><article key={row.malh}><h3>{row.dichvu||`Lịch hẹn #${row.malh}`}</h3>{status(row)}<p>{date(row.ngaygio)}</p><p>{row.nhanvien||'Spa sắp xếp'}</p>{actions(row)}</article>):<Empty description="Không có lịch hẹn phù hợp"/>}</div>:
    <Table rowKey="malh" dataSource={visible} pagination={{pageSize:8,hideOnSinglePage:true}} scroll={{x:640}} columns={[{title:'Dịch vụ / thời gian',key:'service',render:(_,row)=><><strong>{row.dichvu}</strong><p>{date(row.ngaygio)}</p></>},{title:'Trạng thái',key:'status',render:(_,row)=>status(row)},{title:'Thao tác',key:'actions',render:(_,row)=>actions(row)}]}/>}
    <Drawer title={detail?`Lịch hẹn #${detail.malh}`:'Chi tiết lịch hẹn'} open={!!detail} onClose={()=>setDetail(undefined)} width={520}>
      {detail&&<Descriptions column={1} items={[{key:'service',label:'Dịch vụ',children:detail.dichvu},{key:'date',label:'Thời gian',children:date(detail.ngaygio)},{key:'staff',label:'Nhân viên',children:detail.nhanvien||'Spa sắp xếp'},{key:'status',label:'Trạng thái',children:status(detail)},{key:'note',label:'Ghi chú',children:detail.ghichu||'Không có'}]}/>}
    </Drawer>
  </>;
}
function Invoices({rows}:{rows:Invoice[]}) {
  const [filter,setFilter]=useState('all');
  const [detail,setDetail]=useState<Invoice>();
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(false);
  const mobile=useMobile();
  const request=useRef<AbortController>();
  useEffect(()=>()=>request.current?.abort(),[]);
  const view=async(id:number)=>{request.current?.abort();const controller=new AbortController();request.current=controller;setLoading(true);setError('');try{const data=await customerApi<Invoice>(`/api/payment/invoices/${id}`,{signal:controller.signal});if(!controller.signal.aborted)setDetail(data);}catch(e){if(!controller.signal.aborted)setError((e as Error).message);}finally{if(request.current===controller)setLoading(false);}};
  const actions=(row:Invoice)=><Space wrap><Button onClick={()=>view(row.mahd)}>Chi tiết</Button>{row.trangthai==='Chưa thanh toán'&&<Button type="primary" onClick={()=>window.LoyaltyPayment.openCustomerInvoice(row.mahd).catch(e=>setError(e.message))}>Tiếp tục thanh toán</Button>}</Space>;
  const visible=rows.filter(row=>filter==='all'||row.trangthai===filter);
  return <>
    <Space className="customer-account-toolbar" wrap><label htmlFor="invoice-filter">Trạng thái</label><Select id="invoice-filter" value={filter} onChange={setFilter} options={[{value:'all',label:'Tất cả'},...['Chưa thanh toán','Đã thanh toán','Đã hủy'].map(value=>({value,label:value}))]}/><Button onClick={()=>window.loadUserInvoices()}>Tải lại</Button></Space>
    {error&&<Alert type="error" message={error} role="alert"/>}{loading&&<p role="status">Đang tải chi tiết hóa đơn…</p>}
    {mobile?<div className="customer-account-cards">{visible.length?visible.map(row=><article key={row.mahd}><h3>Hóa đơn #{row.mahd}</h3><Tag>{row.trangthai}</Tag><p>{date(row.ngaylap)}</p><p><strong>{price(row.payable_amount??row.tongtien)}</strong></p>{actions(row)}</article>):<Empty description="Chưa có hóa đơn phù hợp"/>}</div>:
    <Table rowKey="mahd" dataSource={visible} pagination={{pageSize:8,hideOnSinglePage:true}} scroll={{x:640}} columns={[{title:'Hóa đơn',dataIndex:'mahd',render:id=>`#${id}`},{title:'Cần thanh toán',key:'amount',render:(_,row)=>price(row.payable_amount??row.tongtien)},{title:'Trạng thái',dataIndex:'trangthai',render:value=><Tag>{value}</Tag>},{title:'Thao tác',key:'actions',render:(_,row)=>actions(row)}]}/>}
    <Drawer title={detail?`Hóa đơn #${detail.mahd}`:'Chi tiết hóa đơn'} open={!!detail} onClose={()=>setDetail(undefined)} width={520}>
      {detail&&<><Descriptions column={1} items={[{key:'status',label:'Trạng thái',children:detail.trangthai},{key:'total',label:'Tạm tính',children:price(detail.original_total??detail.tongtien)},{key:'voucher',label:'Giảm bằng voucher',children:price(detail.reward_discount??0)},{key:'points',label:'Giảm bằng điểm',children:price(detail.loyalty_discount??0)},{key:'due',label:'Cần thanh toán',children:<strong>{price(detail.payable_amount??detail.tongtien)}</strong>}]}/>{detail.chitiet?.map((line,i)=><p key={i}>{line.tendv} · {line.soluong} × {price(line.dongia)}</p>)}</>}
    </Drawer>
  </>;
}
export const customerAccount: Bridge={
  setProfile(user){profile=user;if(document.getElementById('edit-section')?.classList.contains('active'))this.showSection('edit');},
  showSection(section){if(section==='edit'&&profile)render('customer-edit-root',<EditProfile user={profile}/>);if(section==='password')render('customer-password-root',<PasswordForm/>);},
  appointments(rows){render('appointmentsList',<Appointments rows={rows}/>,true);},
  invoices(rows){render('invoicesList',<Invoices rows={rows}/>,true);},
  error(section,message){render(section==='appointments'?'appointmentsList':'invoicesList',<Alert type="error" message={message} action={<Button onClick={()=>section==='appointments'?window.loadUserAppointments():window.loadUserInvoices()}>Thử lại</Button>}/>,true);},
};
window.addEventListener('pagehide',()=>{roots.forEach(root=>root.unmount());roots.clear();});
