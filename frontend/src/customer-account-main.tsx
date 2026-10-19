import './customer-main';
import './customer/account.css';
import type { Bridge, Profile } from './customer/account-panels';
import { customerTreatments } from './customer/treatments';

// The existing PackageCare adapter remains the sole data/event owner.
window.CustomerTreatments = customerTreatments;

let profile: Profile | undefined;
let implementation: Bridge | undefined;
let pending: Promise<typeof import('./customer/account-panels')> | undefined;
function load(action: (panels: Bridge) => void) {
  void (pending ||= import('./customer/account-panels')).then(module => {
    implementation = module.customerAccount;
    if (profile) implementation.setProfile(profile);
    action(implementation);
  }).catch(() => {
    pending = undefined;
    if (document.getElementById('account-entry-error')) return;
    const notice = document.createElement('p');
    notice.id = 'account-entry-error'; notice.setAttribute('role', 'alert');
    notice.textContent = 'Chưa tải được giao diện tài khoản. ';
    const link = document.createElement('a');
    const url = new URL(location.href); url.searchParams.set('ui', 'legacy');
    link.href = url.pathname + url.search + url.hash; link.textContent = 'Mở giao diện trước đây';
    notice.append(link); document.querySelector('.profile-content')?.prepend(notice);
  });
}
// Existing treatment/reward/review/preference subtrees retain one legacy owner.
window.CustomerAccount = {
  setProfile(user) { profile = user; implementation?.setProfile(user); },
  showSection(section) { if (section === 'edit' || section === 'password') load(panels => panels.showSection(section)); },
  appointments(rows) { load(panels => panels.appointments(rows)); },
  invoices(rows) { load(panels => panels.invoices(rows)); },
  error(section, message) { load(panels => panels.error(section, message)); },
};
