<p align="center">
  <img src="static/description/banner.png" alt="ChromeBlue Elite Backend Theme" width="100%">
</p>

<h1 align="center">ChromeBlue Elite — Odoo 19 Backend Theme</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Odoo-19.0-714B67" alt="Odoo 19.0">
  <img src="https://img.shields.io/badge/license-LGPL--3.0-blue" alt="LGPL-3.0">
  <img src="https://img.shields.io/badge/python-none-lightgrey" alt="No Python code">
  <img src="https://img.shields.io/badge/data%20model-untouched-success" alt="No data model changes">
</p>

<p align="center">
  A responsive visual reskin of the Odoo 19 backend — persistent app sidebar, light/dark mode,
  bundled webfonts and a fully themed web client. Technical name: <code>bluegray_modern_theme</code>.
</p>

---

## What it is

ChromeBlue Elite restyles the entire Odoo web client from the asset bundle alone. It ships **no
Python models, no controllers, no security rules and no data migrations** — everything it adds
lives in `web.assets_backend`. Activate it and the look changes; uninstall it and Odoo returns to
stock. Nothing in your database is touched either way.

## Features

### Design system

| | |
|---|---|
| **Design tokens** | One `:root` block of `--cmt-*` custom properties drives every colour, radius, shadow and font in the theme. Change a token, the whole UI follows. |
| **Palette** | Deep Indigo `#3959b0` primary with Ocean Blue `#0284c7` accents over tiered white surfaces. |
| **Shape & elevation** | 6/8/12/16px radius scale, soft multi-layer shadows, "chrome border" (1px stroke + inset white reflection) on raised surfaces. |
| **Typography** | Inter for UI text, Poppins for labels and numerics — both bundled in-module as latin-subset `woff2`, so there is no `fonts.googleapis.com` request and nothing breaks offline or under a strict CSP. |

### Interface

- **Persistent app sidebar** replacing Odoo's apps dropdown — every app the user can reach, always
  visible, with the current app marked by an accent spine. Toggled from the navbar's grid button;
  the open/closed choice is remembered per browser.
- **Bundled app artwork** — 55+ icons covering the standard Odoo apps. They are single-colour and
  painted through a CSS mask rather than drawn as images, so one icon set carries all three states:
  grey at rest, blue on hover, a stronger blue for the app you are in. Apps with no bundled artwork
  fall back to their own Odoo icon, then to a neutral placeholder.
- **Light / dark mode** — switched from the sidebar footer, applied instantly, remembered per
  browser. The palette hangs off a single `data-cmt-theme` attribute on `<html>`, so dialogs,
  popovers and tooltips (which Odoo portals out to `<body>`) are covered too.
- **Control panel as a page header** — the last breadcrumb is promoted to a 32px headline, actions
  sit right, no divider rule.
- **Top navbar** retinted through Odoo's own `--NavBar-*` properties instead of fought with
  `!important`.
- **Kanban boards** — 320px stage columns on a 24px gutter, glassmorphic cards with an accent spine
  on hover and on won opportunities.
- **CRM pipeline stat banner** — a four-card KPI readout above the pipeline (stage counts, expected
  revenue, conversion). Computed entirely from the grouped data already in memory: **no extra RPC**.
- **Responsive** — tablet and phone breakpoints mirroring Bootstrap's; below `md` the rail steps
  aside for Odoo's own slide-in app menu.

## Requirements

| | |
|---|---|
| Odoo | 19.0 (Community or Enterprise) |
| Depends | `web`, `base_setup` |
| Optional | `crm` — required only for the pipeline stat banner |

## Installation

```bash
# 1. Clone into your addons path
cd /path/to/odoo/custom-addons
git clone https://github.com/NandiniGohel/odoo_theme_backend.git bluegray_modern_theme

# 2. Restart Odoo with the addons path registered
./odoo-bin -c odoo.conf -u bluegray_modern_theme
```

> **Note** — the directory name must be `bluegray_modern_theme`; that is the module's technical
> name and the asset paths are absolute references to it.

Then in Odoo: **Apps → Update Apps List → search "ChromeBlue Elite" → Activate**.

The module is listed as an application, so it gets its own card under Apps rather than hiding
behind the "Extra" filter. It never installs itself (`auto_install: False`) — dropping it in the
addons path changes nothing until someone activates it.

### While developing

SCSS is compiled server-side and cached in `ir.attachment`. To see edits without restarting:

```bash
./odoo-bin -c odoo.conf --dev=all
```

Otherwise bump the assets (Settings → Technical → Regenerate Assets Bundles) and hard-refresh.

## Usage

| Action | Where |
|---|---|
| Show / hide the app sidebar | Grid button in the top navbar (`Alt` + `H`) |
| Switch light ↔ dark | Sidebar footer, bottom-left |
| Reset either preference | Clear `cmt_color_scheme` / `cmt_apps_sidebar_open` from `localStorage` |

Both preferences are client-side only — no server round-trip, no per-user config record, so they
apply instantly and survive a reload.

## Customization

### Recolour the theme

Every visual decision is a token in [`static/src/scss/variables.scss`](static/src/scss/variables.scss):

```scss
:root {
    --cmt-primary: #3959b0;          // brand + primary actions
    --cmt-tertiary: #0284c7;         // status + secondary accents
    --cmt-bg: #f8f9fa;               // the main canvas
    --cmt-surface: #ffffff;          // cards, navbar, panels
    --cmt-text: #111827;
    --cmt-radius-lg: 12px;           // kanban cards
    --cmt-font-sans: 'Inter', …;
}
```

The dark palette is the same token set redeclared under
`:root[data-cmt-theme="dark"]` in [`dark_mode.scss`](static/src/scss/dark_mode.scss) — edit the two
blocks in parallel and both modes stay in step.

### Add an icon for your own app

Drop a single-colour PNG/SVG on a transparent background into
`static/src/image/icons/`, then map it in
[`static/src/js/apps_sidebar.js`](static/src/js/apps_sidebar.js) by the module part of the app's
xmlid:

```js
const ICON_BY_MODULE = {
    my_module: "my-icon.svg",
    // …
};
```

Matching on the module rather than the display name keeps the mapping working in every language.
Apps with no entry fall back to their own Odoo icon, then to `generic-app.svg`.

## Project structure

```
bluegray_modern_theme/
├── __manifest__.py              # assets registration; no data files, no models
├── static/
│   ├── description/             # app-store card: icon, banner, index.html
│   └── src/
│       ├── fonts/               # Inter + Poppins, latin subset (OFL 1.1)
│       ├── image/icons/         # bundled app artwork, one per Odoo app
│       ├── scss/
│       │   ├── variables.scss   # ← every design token lives here
│       │   ├── fonts.scss       # @font-face, bundled not CDN
│       │   ├── base.scss        # canvas, scrollbars, shared primitives
│       │   ├── navbar.scss      # top bar, via --NavBar-* properties
│       │   ├── apps_sidebar.scss
│       │   ├── control_panel.scss
│       │   ├── kanban.scss
│       │   ├── stats_banner.scss
│       │   ├── buttons_misc.scss
│       │   ├── responsive.scss
│       │   └── dark_mode.scss   # loaded last; overrides every surface above
│       ├── js/
│       │   ├── theme_mode.js            # light/dark state + <html> attribute
│       │   ├── apps_sidebar.js          # the rail component + icon mapping
│       │   ├── apps_sidebar_patch.js    # slots it into WebClient / NavBar
│       │   ├── crm_pipeline_stats.js    # KPI cards, computed in memory
│       │   └── crm_pipeline_stats_patch.js
│       └── xml/                 # OWL templates + inherited core templates
└── views/
    └── crm_lead_views.xml       # optional CRM card restyle — see below
```

> `views/crm_lead_views.xml` restyles the CRM pipeline card (title + priority on one row, contact
> line, revenue and assignee in the footer). It is **not** registered in the manifest's `data`
> list, because loading it would make the theme hard-depend on `crm`. To enable it, add `crm` to
> `depends` and the file to `data`.

## How it works

The theme layers three techniques, in order of preference:

1. **Odoo's own custom properties** — `--NavBar-*`, `--Kanban-*`, `--Notebook__*` and friends are
   redefined rather than overridden, so core keeps control of layout and the theme only supplies
   colour.
2. **Bootstrap runtime variables** — retargeted at document and component level. Odoo 19 Community
   compiles with `$enable-dark-mode: false`, so Bootstrap's own `[data-bs-theme=dark]` block never
   exists; the dark palette re-seeds those variables instead.
3. **Direct overrides**, last resort — for surfaces Odoo compiles straight into SCSS literals
   (`$o-view-background-color`, `$o-webclient-background-color`, `$white`) that no runtime variable
   can reach. Each of these is commented with the core file and rule it answers to.

Every dark-mode rule is scoped under the `data-cmt-theme="dark"` attribute, so light mode is never
in the cascade fight.

## Known limitations

- Odoo's slide-in app menu on small screens (below `md`) is left as-is.
- **Graph views stay light on purpose.** Odoo draws chart axis labels onto the canvas from JS,
  taking the colour from a cookie that Community pins to `"light"` server-side. Darkening the panel
  would put near-black text on a near-black background, so the chart is given an explicit light
  card instead.
- Dark mode covers this theme's surfaces plus the main list / form / kanban / dialog chrome.
  Deeper corners — some reports, iframes and third-party widgets — can still show light patches.
- No fixed bottom footer bar and no floating action button.

## Uninstall

Apps → ChromeBlue Elite Backend Theme → Uninstall. The backend returns to stock Odoo immediately.
Because the module owns no models, fields or records, there is nothing to migrate and nothing to
lose.

## License

[LGPL-3.0](https://www.gnu.org/licenses/lgpl-3.0.html).

Bundled fonts — Inter and Poppins — are under the
[SIL Open Font License 1.1](https://openfontlicense.org/).
