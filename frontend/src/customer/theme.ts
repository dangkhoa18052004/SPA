import type { ThemeConfig } from 'antd';

// Read the same CSS tokens used by public and booking. Called inside the customer
// document only; the staff portal never imports this module or its stylesheet.
export function customerTheme(): ThemeConfig {
  const css = getComputedStyle(document.body);
  const token = (name: string, fallback: string) => css.getPropertyValue(`--customer-${name}`).trim() || fallback;
  return { token: {
    colorPrimary: token('primary', '#425f49'), colorText: token('text', '#2e3c30'),
    colorTextSecondary: token('muted', '#606e60'), colorBgLayout: token('background', '#f7f7f2'),
    colorTextPlaceholder: token('muted', '#606e60'),
    colorError: '#a62b2b', colorErrorHover: '#8d2424', colorErrorActive: '#7a1f1f',
    colorBgContainer: token('surface', '#fff'), colorBorder: token('border', '#dce3d8'),
    fontFamily: token('font', '-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'),
    fontSize: 16, controlHeight: 44, borderRadius: 10, borderRadiusLG: 16,
    zIndexPopupBase: 1100, motion: !matchMedia('(prefers-reduced-motion: reduce)').matches,
  } };
}
