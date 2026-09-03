{
    'name': 'BlueNova Backend Theme',
    'version': '19.0.1.0.0',
    'category': 'Themes/Backend',
    'summary': 'Premium glossy metallic backend theme with deep royal blue, electric blue accents, silver chrome finishes and modern glassmorphic effects',
    "author": "Strats360 Technolabs-LLP",
    "company": "Strats360 Technolabs-LLP",
    "maintainer": "Strats360 Technolabs-LLP",
    "website": "https://strats360.com/",
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
• Editable light-mode colours under Settings > Theme Settings, with an
  uploadable sidebar brand image and JSON preset import / export / reset.
  Changes apply on save — no asset rebuild or server restart.
• The same theme on the login, signup and reset-password pages, including
  dark mode, an optional logo and background image, and a tagline.
• A themed Dashboard app built to the DESIGN.md reference: gradient hero
  cards with a 30-day trend, metric cards with sparklines and status
  pills, a 30-day column chart with one series per app, a recent-activity
  feed, quick "New …" actions and a preview of the user's own open work —
  all for whichever apps are installed and readable by the user, and
  optionally opened automatically after login. A floating chat bubble in
  the corner lists the user's Discuss conversations and opens any of them
  in place, with its messages and a composer — OdooBot answers, and new
  messages arrive live — while "Open Discuss" hands over to the real
  thing. Present only where Discuss itself is installed.
• An optional themed public page at / for anonymous visitors. Off by
  default, and it stands down when the `website` module is installed.

Uninstall the module to instantly return to the default Odoo look.
No data is modified.
    """,
    'license': 'LGPL-3',
    'depends': [
        'web',
        'base_setup',
    ],
    'data': [
        'security/ir.model.access.csv',

        # Renders the colours saved under Settings > Theme Settings into
        # the backend page head, after the compiled bundles.
        'views/theme_styles.xml',

        # The unauthenticated surfaces. Both render through
        # web.frontend_layout and read the same colours as the backend;
        # neither needs a dependency beyond `web`.
        'views/auth_theme.xml',
        'views/public_home.xml',

        # The landing dashboard: client action + its app menu.
        'views/home_dashboard_actions.xml',

        'wizard/theme_import_wizard_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        # ── Brand colours ────────────────────────────────────────
        # ('prepend', …), not a plain entry: core's own
        # primary_variables.scss declares $o-brand-primary and friends
        # with `!default` and then derives a dozen more variables from
        # them on the spot. Loading after it would win the assignment
        # and lose every derivation. See the header comment in the file
        # itself.
        'web._assets_primary_variables': [
            ('prepend', 'bluenova_backend_theme/static/src/scss/primary_variables.scss'),
        ],

        # ── The web client ───────────────────────────────────────
        # Appended to the end of web.assets_backend, so these rules land
        # after core's and win at equal specificity.
        'web.assets_backend': [
            'bluenova_backend_theme/static/src/scss/fonts.scss',
            'bluenova_backend_theme/static/src/scss/variables.scss',
            'bluenova_backend_theme/static/src/scss/base.scss',
            'bluenova_backend_theme/static/src/scss/navbar.scss',
            'bluenova_backend_theme/static/src/scss/apps_sidebar.scss',
            'bluenova_backend_theme/static/src/scss/control_panel.scss',
            'bluenova_backend_theme/static/src/scss/kanban.scss',
            'bluenova_backend_theme/static/src/scss/stats_banner.scss',
            # After apps_sidebar.scss and base.scss: it uses the
            # cmt-masked-icon and cmt-label-sm mixins they define, and a
            # bundle is compiled as one SCSS document in this order.
            'bluenova_backend_theme/static/src/scss/home_dashboard.scss',
            # The floating chat bubble the dashboard renders. Its own
            # file rather than a section of home_dashboard.scss: it is
            # pinned to the viewport rather than laid out in one of that
            # file's bands, and it shares none of its grids.
            'bluenova_backend_theme/static/src/scss/chat_launcher.scss',
            'bluenova_backend_theme/static/src/scss/settings_page.scss',
            'bluenova_backend_theme/static/src/scss/buttons_misc.scss',
            # After every stylesheet that styles a component itself: it
            # only redirects core's compiled brand literals at the token,
            # so it has to land after core's rules (any position in this
            # bundle does that) but must not sit in front of a theme rule
            # that deliberately paints the same surface something else.
            #
            # This file is what makes the Primary picker work in *light*
            # mode. Dark mode never needed it: dark_mode.scss already
            # restates core's surfaces in --cmt-* tokens, so the picker
            # reaches them through the token. Light mode has no such
            # sweep — core's light surfaces are compiled literals baked
            # from $o-brand-primary at build time, which no runtime
            # custom property can reach. Drop this entry and the picker
            # silently goes back to working in one scheme only.
            'bluenova_backend_theme/static/src/scss/brand_bridge.scss',

            # Then device rules. Every file above states the desktop
            # case; this one adapts those surfaces down to tablet/phone
            # and up to wide screens, so it has to follow them all.
            # Before dark_mode.scss, which only swaps colour and must
            # keep winning at every size.
            'bluenova_backend_theme/static/src/scss/responsive.scss',
            # Last: overrides every surface above once dark mode is on.
            'bluenova_backend_theme/static/src/scss/dark_mode.scss',

            'bluenova_backend_theme/static/src/js/theme_mode.js',
            'bluenova_backend_theme/static/src/js/apps_sidebar_state.js',
            'bluenova_backend_theme/static/src/js/apps_sidebar.js',
            'bluenova_backend_theme/static/src/js/apps_sidebar_patch.js',
            # Before home_dashboard.js, which imports it.
            'bluenova_backend_theme/static/src/js/chat_launcher.js',
            'bluenova_backend_theme/static/src/js/home_dashboard.js',

            'bluenova_backend_theme/static/src/xml/apps_sidebar.xml',
            'bluenova_backend_theme/static/src/xml/home_dashboard.xml',
            'bluenova_backend_theme/static/src/xml/chat_launcher.xml',
        ],

        # ── Login, signup, reset-password and the public page ────
        # These render through web.frontend_layout, which pulls
        # web.assets_frontend — a different bundle from the backend one,
        # so none of the stylesheets above reach them.
        #
        # Only four files, not the whole backend set:
        #
        #   fonts.scss     — the @font-face rules; the bundles are
        #                    compiled separately, so the backend's copy
        #                    is not shared.
        #   variables.scss — the cmt token block every rule below reads.
        #   auth_pages.scss / public_home.scss — the surfaces themselves.
        #
        # dark_mode.scss is deliberately left out. It is written against
        # backend DOM that does not exist here; the two files below
        # carry their own :root[data-cmt-theme="dark"] blocks for the
        # handful of surfaces they own.
        #
        # primary_variables.scss needs no entry: web.assets_frontend
        # includes web._assets_frontend_helpers, which includes
        # web._assets_primary_variables — the same bundle the block at
        # the top of this dict prepends to.
        'web.assets_frontend': [
            'bluenova_backend_theme/static/src/scss/fonts.scss',
            'bluenova_backend_theme/static/src/scss/variables.scss',
            'bluenova_backend_theme/static/src/scss/auth_pages.scss',
            'bluenova_backend_theme/static/src/scss/public_home.scss',
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
