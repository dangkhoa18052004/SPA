import { expect, it } from 'vitest';
import { price, serviceCard } from './catalog';

it('renders API text as text and preserves the booking service id', () => {
  const html = serviceCard({madv:7,tendv:'<img src=x onerror=alert(1)>',mota:'" onclick="alert(2)',gia:0});
  expect(html).toContain('&lt;img');
  expect(html).not.toContain('<img src=x');
  expect(html).toContain('/appointments/create?service=7');
  expect(html).not.toMatch(/<[^>]*\sonclick\s*=/i);
});
it('distinguishes zero from a missing price', () => {
  expect(price(0)).toContain('0');
  expect(price(null)).toBe('Liên hệ');
  expect(price('invalid')).toBe('Liên hệ');
});
