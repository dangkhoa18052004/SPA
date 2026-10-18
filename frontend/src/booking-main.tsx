import React from 'react';
import { createRoot } from 'react-dom/client';
import BookingPage from './customer/Booking';
import { Button, Card } from './customer/ui';
import './customer/booking.css';

class BookingBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <Card><h2 className="mb-4 text-xl font-semibold">Chưa tải được màn đặt lịch</h2><p className="mb-5">Vui lòng tải lại trang để tiếp tục.</p><Button onClick={() => location.reload()}>Tải lại</Button></Card> : this.props.children; }
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><BookingBoundary><BookingPage /></BookingBoundary></React.StrictMode>);
