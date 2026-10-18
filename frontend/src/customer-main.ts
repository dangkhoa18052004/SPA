import './customer/tokens.css';
import './customer/public.css';
import { serviceCard, escapeHtml, price } from './customer/catalog';

window.CustomerCatalog = { serviceCard, escapeHtml, price };

// A pasted SMS/email code fills the existing six-input OTP contract.
const otpInputs = [...document.querySelectorAll<HTMLInputElement>('.otp-input')];
otpInputs.forEach((input, index) => {
  input.inputMode = 'numeric';
  input.setAttribute('aria-label', `Chữ số OTP ${index + 1}`);
  input.autocomplete = index === 0 ? 'one-time-code' : 'off';
  input.addEventListener('paste', event => {
    const code = event.clipboardData?.getData('text').replace(/\D/g, '') || '';
    if (!code) return;
    event.preventDefault();
    [...code].slice(0, otpInputs.length - index).forEach((digit, offset) => { otpInputs[index + offset].value = digit; });
    otpInputs[Math.min(index + code.length, otpInputs.length) - 1].focus();
  });
});

// Jinja and legacy scripts retain DOM ownership. This entry adds semantics only.
document.querySelectorAll<HTMLAnchorElement>('.navbar .nav-link, .mobile-bottom-nav a').forEach(link => {
  const target = new URL(link.href);
  const active = !target.hash && (target.pathname === location.pathname ||
    target.pathname !== '/' && location.pathname.startsWith(`${target.pathname}/`));
  if (active) link.setAttribute('aria-current', 'page');
  if (link.classList.contains('nav-link') && target.pathname === '/packages') link.textContent = 'Gói dịch vụ';
});

const music = document.getElementById('musicFloat');
if (music) {
  music.setAttribute('role', 'button');
  music.tabIndex = 0;
  music.setAttribute('aria-label', 'Bật hoặc tắt nhạc thư giãn');
  music.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); music.click(); } });
}
const avatarUpload = document.querySelector<HTMLElement>('.avatar-upload');
if (avatarUpload) {
  avatarUpload.setAttribute('role', 'button');
  avatarUpload.setAttribute('aria-label', 'Thay ảnh đại diện');
  avatarUpload.tabIndex = 0;
  avatarUpload.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); document.getElementById('avatarInput')?.click(); } });
}

for (const [buttonId, panelId] of [['userBtn', 'userDropdown'], ['langBtn', 'langDropdown'], ['chatFloat', 'chatBox']]) {
  const button = document.getElementById(buttonId);
  const panel = document.getElementById(panelId);
  if (!button || !panel) continue;
  button.setAttribute('aria-controls', panelId);
  const sync = () => button.setAttribute('aria-expanded', String(panel.classList.contains('show')));
  sync();
  new MutationObserver(sync).observe(panel, { attributes: true, attributeFilter: ['class'] });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && panel.classList.contains('show')) {
      panel.classList.remove('show');
      button.focus();
    }
  });
}
