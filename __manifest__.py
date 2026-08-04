{
    'name': 'BlueNova Backend Theme',
    'version': '19.0.1.0.0',
    'category': 'Themes/Backend',
    'summary': 'Premium glossy metallic backend theme with deep royal blue, electric blue accents, silver chrome finishes and modern glassmorphic effects',
    'description': """
BlueNova Backend Theme
======================

A luxurious, modern visual reskin of the Odoo backend.

Key Features:
• Deep Royal Blue (#003087) + Electric Blue (#00AEEF) accents
• Cool Silver / Chrome metallic gradients & glossy effects
• Glassmorphic panels, cards and dropdowns
• Premium 3D-style icons and soft multi-layer shadows
• Clean white main content area with subtle depth
• Fully supports Light & Dark mode
• Applies to the entire web client (navbar, sidebar, control panel, kanban, list, form views, etc.)

Uninstall the module to instantly return to the default Odoo look.
No data is modified.
    """,
    'author': 'Custom',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'web',
        'base_setup',
    ],
    'data': [
        # Uncomment when you add the files
        # 'views/assets.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bluegray_modern_theme/static/src/scss/fonts.scss',
            'bluegray_modern_theme/static/src/scss/variables.scss',
            'bluegray_modern_theme/static/src/scss/base.scss',
            'bluegray_modern_theme/static/src/scss/navbar.scss',
            'bluegray_modern_theme/static/src/scss/apps_sidebar.scss',
            'bluegray_modern_theme/static/src/scss/control_panel.scss',
            'bluegray_modern_theme/static/src/scss/kanban.scss',
            'bluegray_modern_theme/static/src/scss/stats_banner.scss',
            'bluegray_modern_theme/static/src/scss/buttons_misc.scss',
            'bluegray_modern_theme/static/src/scss/responsive.scss',
            # Last: overrides every surface above once dark mode is on.
            'bluegray_modern_theme/static/src/scss/dark_mode.scss',
            'bluegray_modern_theme/static/src/js/theme_mode.js',
            'bluegray_modern_theme/static/src/js/apps_sidebar.js',
            'bluegray_modern_theme/static/src/js/apps_sidebar_patch.js',
            'bluegray_modern_theme/static/src/js/crm_pipeline_stats.js',
            'bluegray_modern_theme/static/src/js/crm_pipeline_stats_patch.js',
            'bluegray_modern_theme/static/src/xml/apps_sidebar.xml',
            'bluegray_modern_theme/static/src/xml/crm_pipeline_stats.xml',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    # Listed as an app so it gets its own card under Apps (the Apps action
    # filters on application = True) with an Activate button, instead of
    # only showing up under the "Extra" filter.
    'application': True,
    # Never turn itself on: the theme is only applied once someone activates
    # it from Apps, even though the module sits in the addons path.
    'auto_install': False,
}
