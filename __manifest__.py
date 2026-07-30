{
    'name': 'Modern CRM Backend Theme',
    'version': '19.0.1.5.0',
    'category': 'Sales/CRM',
    'summary': 'Modern, responsive visual reskin of the Odoo backend (navbar, control panel, kanban cards) for CRM',
    'description': """
Modern CRM Backend Theme
=========================
Front-end reskin of the Odoo web client based on the "Enterprise Elite"
design spec, applied to the web.assets_backend bundle. Does NOT modify any
Python models, controllers, security rules or business logic. Safe to
install/uninstall at any time without touching your data.

What it changes:
- Design tokens: Deep Indigo primary, tiered white surfaces, 8/12/16px radii
- Typography: Inter and Poppins, bundled in-module (no CDN request)
- Top navbar colors/typography
- Left app sidebar replacing Odoo's apps dropdown, with bundled app icons
- Light/dark mode, switched from the sidebar footer and remembered per browser
- Control panel styled as a page header (headline-lg title)
- Kanban board: 320px stage columns, glassmorphic cards with an accent spine
- A live stat-card banner above the CRM pipeline (no extra RPC)
- Buttons, badges, spacing, border-radius, shadows
- Responsive breakpoints for tablet/mobile

What it deliberately does NOT do (see PROMPT.md for how to extend):
- Does not replace Odoo's slide-in app menu on small screens (below md)
- Dark mode covers the backend surfaces this theme styles plus the main
  list/form/kanban/dialog chrome. Odoo compiles most other colours into
  SCSS ($enable-dark-mode is false in core), so deeper corners - some
  reports, iframes and third-party widgets - can still show light patches
- Does not add the fixed bottom footer bar or the floating action button
""",
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['crm', 'web'],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'crm_modern_theme/static/src/scss/fonts.scss',
            'crm_modern_theme/static/src/scss/variables.scss',
            'crm_modern_theme/static/src/scss/base.scss',
            'crm_modern_theme/static/src/scss/navbar.scss',
            'crm_modern_theme/static/src/scss/apps_sidebar.scss',
            'crm_modern_theme/static/src/scss/control_panel.scss',
            'crm_modern_theme/static/src/scss/kanban.scss',
            'crm_modern_theme/static/src/scss/stats_banner.scss',
            'crm_modern_theme/static/src/scss/buttons_misc.scss',
            'crm_modern_theme/static/src/scss/responsive.scss',
            # Last: overrides every surface above once dark mode is on.
            'crm_modern_theme/static/src/scss/dark_mode.scss',
            'crm_modern_theme/static/src/js/theme_mode.js',
            'crm_modern_theme/static/src/js/apps_sidebar.js',
            'crm_modern_theme/static/src/js/apps_sidebar_patch.js',
            'crm_modern_theme/static/src/js/crm_pipeline_stats.js',
            'crm_modern_theme/static/src/js/crm_pipeline_stats_patch.js',
            'crm_modern_theme/static/src/xml/apps_sidebar.xml',
            'crm_modern_theme/static/src/xml/crm_pipeline_stats.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
