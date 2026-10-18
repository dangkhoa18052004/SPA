"""Resolve built UI entries without making an unbuilt release break legacy pages."""
import json
from pathlib import Path
from flask import current_app, render_template, request


def portal_assets(source, *, require_complete=False):
    path = Path(current_app.static_folder) / 'portal/.vite/manifest.json'
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
        entry = manifest[source]
        if not (path.parent.parent / entry['file']).is_file():
            return None
        styles = []
        visited = set()

        def validate(key, seen):
            if key in seen:
                return
            seen.add(key)
            value = manifest[key]
            for file in [value['file'], *value.get('css', [])]:
                if not (path.parent.parent / file).is_file():
                    raise OSError('Missing UI asset')
            for dependency in value.get('imports', []) + value.get('dynamicImports', []):
                validate(dependency, seen)

        if require_complete:
            validate(source, set())

        def collect(key):
            if key in visited:
                return
            visited.add(key)
            value = manifest[key] if require_complete else manifest.get(key, {})
            for dependency in value.get('imports', []):
                collect(dependency)
            for css in value.get('css', []):
                if css not in styles:
                    styles.append(css)

        collect(source)
        return dict(portal_styles=styles, portal_entry=entry['file'],
                    portal_version=int(path.stat().st_mtime), portal_ready=True)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def customer_public_assets():
    """Progressively enhance public Jinja pages only when the full entry exists."""
    if (not current_app.config.get('CUSTOMER_PUBLIC_UI_ENABLED')
            or request.args.get('ui') == 'legacy'):
        return None
    assets = portal_assets('src/customer-main.ts', require_complete=True)
    return dict(styles=assets['portal_styles'], entry=assets['portal_entry']) if assets else None


def customer_account_assets():
    if (not current_app.config.get('CUSTOMER_ACCOUNT_REACT_ENABLED')
            or request.args.get('ui') == 'legacy'):
        return None
    assets = portal_assets('src/customer-account-main.tsx', require_complete=True)
    return dict(styles=assets['portal_styles'], entry=assets['portal_entry']) if assets else None


def admin_portal_page(title, flag=None):
    """Render the shared React admin shell, or None to keep the legacy page.

    BUSINESS_PORTAL_ENABLED switches the shell; `flag` switches one group of screens; ?ui=legacy
    and an unbuilt release always fall back to the server-rendered page.
    """
    if not current_app.config.get('BUSINESS_PORTAL_ENABLED') or request.args.get('ui') == 'legacy':
        return None
    if flag and not current_app.config.get(flag):
        return None
    assets = portal_assets('src/main.tsx')
    return render_template('operations/portal.html', portal_title=title, **assets) if assets else None
