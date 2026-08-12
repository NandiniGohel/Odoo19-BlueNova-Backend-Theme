import base64
import json
import logging
import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Attachment names the uploaded images are stored under. Looked up by
# name rather than tracked through a config parameter so a half-finished
# save can never leave a dangling id behind.
BRAND_IMAGE_NAME = "bluenova_backend_theme.sidebar_brand_image"
LOGIN_BG_IMAGE_NAME = "bluenova_backend_theme.login_background_image"
LOGIN_BG_IMAGE_DARK_NAME = "bluenova_backend_theme.login_background_image_dark"

# What a colour field is allowed to contain before it reaches a
# stylesheet. The values are interpolated straight into a <style> block
# rendered into the backend page, so an unvalidated string here would be
# a CSS injection with an admin-only trigger — `#fff; } html { display:
# none } :root {` is a defacement, and a url() is an external request
# with the user's referrer on it. Only the two forms the colour picker
# itself emits are accepted.
COLOR_RE = re.compile(r"^(#[0-9A-Fa-f]{3,8}|rgba?\([\d\s.,%]+\))$")

# Bounds for the hero typography numbers. These are interpolated into a
# stylesheet exactly like the colours are, so they get the same
# treatment: a range check on the way in and again on the way out. They
# are plain integers, so the check is a range rather than a pattern —
# but the reason for it is the same, and the upper bounds also stop a
# fat-fingered 600px title from painting a page nobody can read.
METRIC_BOUNDS = {
    "size": (8, 200),      # px
    "weight": (100, 900),  # CSS font-weight keywords, numeric form
}


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ── Field → CSS custom property ──────────────────────────────
    # The single source of truth tying this screen to the stylesheets.
    # Kept explicit rather than derived from the field name: the tokens
    # predate the settings screen and do not follow one naming rule
    # (theme_color_background paints --cmt-bg, theme_color_muted_text
    # paints --cmt-text-muted), and silently mapping to a token nothing
    # consumes would produce a picker that appears to work and changes
    # nothing.
    #
    # Every token here is declared in static/src/scss/variables.scss
    # under "Settings-driven tokens". Add to one and you must add to
    # the other.
    _THEME_CSS_VARS = {
        # Core colours
        "theme_color_primary": "--cmt-primary",
        "theme_color_background": "--cmt-bg",
        "theme_color_text": "--cmt-text",
        "theme_color_muted_text": "--cmt-text-muted",
        "theme_color_text_hover": "--cmt-text-hover",
        "theme_color_button": "--cmt-button-bg",
        "theme_color_button_text": "--cmt-button-text",
        # Top bar
        "theme_color_topbar_bg": "--cmt-topbar-bg",
        "theme_color_topbar_text": "--cmt-topbar-text",
        "theme_color_search_text": "--cmt-search-text",
        "theme_color_search_placeholder": "--cmt-search-placeholder",
        "theme_color_search_border": "--cmt-search-border",
        "theme_color_search_bg": "--cmt-search-bg",
        # Sidebar base
        "theme_color_sidebar_bg": "--cmt-sidebar-bg",
        # Active menu
        "theme_color_active_app": "--cmt-active-app",
        # Authentication pages
        "theme_color_login_bg": "--cmt-login-bg",
        "theme_color_login_card_bg": "--cmt-login-card-bg",
        "theme_color_auth_action_bg": "--cmt-auth-action-bg",
        "theme_color_auth_action_text": "--cmt-auth-action-text",
        # Semantic
        "theme_color_info": "--cmt-info",
        "theme_color_success": "--cmt-success",
        "theme_color_warning": "--cmt-warning",
        "theme_color_danger": "--cmt-danger",
        # Home page
        "theme_color_home_title": "--cmt-home-title",
        "theme_color_home_lead": "--cmt-home-lead",
    }

    # ── Dark-mode counterparts ───────────────────────────────────
    # A second map rather than more entries in the one above, because
    # the two are emitted under opposite selectors: _get_theme_css()
    # hardcodes `:root:not([data-cmt-theme="dark"])` and
    # _get_theme_css_dark() hardcodes `:root[data-cmt-theme="dark"]`.
    # Merging them would mean one method deciding a scope per field,
    # which is exactly the kind of branch that ends up painting a light
    # colour into dark mode.
    #
    # Note the values: each dark field maps to the *same* token as its
    # light twin. That is the whole mechanism — one token, two rules,
    # and the attribute on <html> picks the winner. Nothing downstream
    # in the SCSS has to know dark mode exists.
    #
    # This mirrors the light map one for one. scss/dark_mode.scss still
    # owns the *default* dark palette — the several hundred surfaces it
    # retints that have no picker — but for the tokens listed here the
    # settings screen now has the last word: dark_mode.scss declares
    # them on `:root[data-cmt-theme="dark"]` from inside the compiled
    # bundle in <head>, and _get_theme_css_dark() emits the same
    # selector from a <style> that lands after it, so equal specificity
    # is broken by document order in the admin's favour.
    _THEME_CSS_VARS_DARK = {
        # Core colours
        "theme_color_primary_dark": "--cmt-primary",
        "theme_color_background_dark": "--cmt-bg",
        "theme_color_text_dark": "--cmt-text",
        "theme_color_muted_text_dark": "--cmt-text-muted",
        "theme_color_text_hover_dark": "--cmt-text-hover",
        "theme_color_button_dark": "--cmt-button-bg",
        "theme_color_button_text_dark": "--cmt-button-text",
        # Top bar
        "theme_color_topbar_bg_dark": "--cmt-topbar-bg",
        "theme_color_topbar_text_dark": "--cmt-topbar-text",
        "theme_color_search_text_dark": "--cmt-search-text",
        "theme_color_search_placeholder_dark": "--cmt-search-placeholder",
        "theme_color_search_border_dark": "--cmt-search-border",
        "theme_color_search_bg_dark": "--cmt-search-bg",
        # Sidebar base
        "theme_color_sidebar_bg_dark": "--cmt-sidebar-bg",
        # Active menu
        "theme_color_active_app_dark": "--cmt-active-app",
        # Authentication pages
        "theme_color_login_bg_dark": "--cmt-login-bg",
        "theme_color_login_card_bg_dark": "--cmt-login-card-bg",
        "theme_color_auth_action_bg_dark": "--cmt-auth-action-bg",
        "theme_color_auth_action_text_dark": "--cmt-auth-action-text",
        # Home page
        "theme_color_home_title_dark": "--cmt-home-title",
        "theme_color_home_lead_dark": "--cmt-home-lead",
    }

    # ── Mode-agnostic colours ────────────────────────────────────
    # These live in _THEME_CSS_VARS above — that is where their field,
    # validation, export and reset come from — but they are *also*
    # re-emitted into the dark block, because they have no dark twin on
    # the settings screen and the light block's
    # `:not([data-cmt-theme="dark"])` selector stops matching the
    # moment dark mode comes on. Without this, picking a Danger red
    # would work in light mode and quietly do nothing in dark.
    _THEME_SHARED_COLOR_FIELDS = (
        "theme_color_info",
        "theme_color_success",
        "theme_color_warning",
        "theme_color_danger",
    )

    # ── Numbers, not colours ─────────────────────────────────────
    # The hero typography controls. A third map because they are neither
    # validated nor scoped like the two above: they are integers, and
    # they are emitted on a bare `:root` because a type scale does not
    # change with the colour scheme — putting them in either of the
    # scheme-scoped blocks would make the hero jump size on the dark
    # switch, or lose its sizing entirely in one of the two modes.
    #
    # field name → (CSS custom property, unit, bounds key)
    _THEME_METRIC_VARS = {
        "theme_home_title_size": ("--cmt-home-title-size", "px", "size"),
        "theme_home_title_weight": ("--cmt-home-title-weight", "", "weight"),
        "theme_home_lead_size": ("--cmt-home-lead-size", "px", "size"),
        "theme_home_lead_weight": ("--cmt-home-lead-weight", "", "weight"),
    }

    # ── Non-colour settings ──────────────────────────────────────
    # Deliberately *not* in the map above: every name in it is run
    # through COLOR_RE on save and interpolated into a stylesheet, so a
    # boolean or a line of text would be rejected there. They are listed
    # here instead so Reset can clear them without a hand-written line
    # per field. Presets stay colours-only, matching the note on the
    # settings screen.
    _THEME_FLAG_PARAMS = (
        "theme_login_use_brand_image",
        "theme_login_tagline",
        "theme_landing_dashboard",
        "theme_public_home_enabled",
    )

    # ── Core colours ─────────────────────────────────────────────
    theme_color_primary = fields.Char(
        string="Primary", default="#3959b0",
        config_parameter="bluenova_backend_theme.color_primary")
    theme_color_background = fields.Char(
        string="Background", default="#f8f9fa",
        config_parameter="bluenova_backend_theme.color_background")
    theme_color_text = fields.Char(
        string="Text", default="#111827",
        config_parameter="bluenova_backend_theme.color_text")
    theme_color_muted_text = fields.Char(
        string="Muted Text", default="#4b5563",
        config_parameter="bluenova_backend_theme.color_muted_text")
    theme_color_text_hover = fields.Char(
        string="Text Hover", default="#111827",
        config_parameter="bluenova_backend_theme.color_text_hover")
    theme_color_button = fields.Char(
        string="Button", default="#3959b0",
        config_parameter="bluenova_backend_theme.color_button")
    theme_color_button_text = fields.Char(
        string="Button Text", default="#ffffff",
        config_parameter="bluenova_backend_theme.color_button_text")

    # ── Top bar ──────────────────────────────────────────────────
    theme_color_topbar_bg = fields.Char(
        string="Top Bar Background", default="#ffffff",
        config_parameter="bluenova_backend_theme.color_topbar_bg")
    theme_color_topbar_text = fields.Char(
        string="Top Bar Text", default="#4b5563",
        config_parameter="bluenova_backend_theme.color_topbar_text")
    theme_color_search_text = fields.Char(
        string="Search Text", default="#111827",
        config_parameter="bluenova_backend_theme.color_search_text")
    theme_color_search_placeholder = fields.Char(
        string="Search Placeholder", default="#9ca3af",
        config_parameter="bluenova_backend_theme.color_search_placeholder")
    theme_color_search_border = fields.Char(
        string="Search Border", default="#e5e7eb",
        config_parameter="bluenova_backend_theme.color_search_border")
    theme_color_search_bg = fields.Char(
        string="Search Background", default="#ffffff",
        config_parameter="bluenova_backend_theme.color_search_bg")

    # ── Sidebar base ─────────────────────────────────────────────
    theme_color_sidebar_bg = fields.Char(
        string="Sidebar Background", default="#ffffff",
        config_parameter="bluenova_backend_theme.color_sidebar_bg")

    # Not a config_parameter: ir.config_parameter is a text column read
    # on nearly every request, and a base64 PNG in it would be carried
    # around for no reason. The image lives in ir.attachment (filestore)
    # and is read/written by hand below.
    theme_sidebar_brand_image = fields.Binary(
        string="Sidebar Brand Background")

    # ── Active menu ──────────────────────────────────────────────
    theme_color_active_app = fields.Char(
        string="Active App", default="#3959b0",
        config_parameter="bluenova_backend_theme.color_active_app")

    # ── Dark mode: core colours ──────────────────────────────────
    # Defaults are the values scss/dark_mode.scss already compiles for
    # these tokens, so opening the screen for the first time shows the
    # theme as it actually looks rather than a row of empty swatches —
    # and saving without touching anything is a no-op.
    theme_color_primary_dark = fields.Char(
        string="Primary (Dark)", default="#7c9aff",
        config_parameter="bluenova_backend_theme.color_primary_dark")
    theme_color_background_dark = fields.Char(
        string="Background (Dark)", default="#0b1120",
        config_parameter="bluenova_backend_theme.color_background_dark")
    theme_color_text_dark = fields.Char(
        string="Text (Dark)", default="#e2e8f0",
        config_parameter="bluenova_backend_theme.color_text_dark")
    theme_color_muted_text_dark = fields.Char(
        string="Muted Text (Dark)", default="#94a3b8",
        config_parameter="bluenova_backend_theme.color_muted_text_dark")
    theme_color_text_hover_dark = fields.Char(
        string="Text Hover (Dark)", default="#f8fafc",
        config_parameter="bluenova_backend_theme.color_text_hover_dark")
    theme_color_button_dark = fields.Char(
        string="Button (Dark)", default="#7c9aff",
        config_parameter="bluenova_backend_theme.color_button_dark")
    theme_color_button_text_dark = fields.Char(
        string="Button Text (Dark)", default="#0b1120",
        config_parameter="bluenova_backend_theme.color_button_text_dark")

    # ── Dark mode: top bar ───────────────────────────────────────
    theme_color_topbar_bg_dark = fields.Char(
        string="Top Bar Background (Dark)", default="#131c31",
        config_parameter="bluenova_backend_theme.color_topbar_bg_dark")
    theme_color_topbar_text_dark = fields.Char(
        string="Top Bar Text (Dark)", default="#94a3b8",
        config_parameter="bluenova_backend_theme.color_topbar_text_dark")
    theme_color_search_text_dark = fields.Char(
        string="Search Text (Dark)", default="#e2e8f0",
        config_parameter="bluenova_backend_theme.color_search_text_dark")
    theme_color_search_placeholder_dark = fields.Char(
        string="Search Placeholder (Dark)", default="#64748b",
        config_parameter="bluenova_backend_theme.color_search_placeholder_dark")
    theme_color_search_border_dark = fields.Char(
        string="Search Border (Dark)", default="#243149",
        config_parameter="bluenova_backend_theme.color_search_border_dark")
    theme_color_search_bg_dark = fields.Char(
        string="Search Background (Dark)", default="#0f1728",
        config_parameter="bluenova_backend_theme.color_search_bg_dark")

    # ── Dark mode: sidebar base ──────────────────────────────────
    theme_color_sidebar_bg_dark = fields.Char(
        string="Sidebar Background (Dark)", default="#131c31",
        config_parameter="bluenova_backend_theme.color_sidebar_bg_dark")

    # ── Dark mode: active menu ───────────────────────────────────
    theme_color_active_app_dark = fields.Char(
        string="Active App (Dark)", default="#7c9aff",
        config_parameter="bluenova_backend_theme.color_active_app_dark")

    # ── Semantic colours ─────────────────────────────────────────
    # Shared: the auth pages' alerts and the backend's status badges
    # read the same four tokens. Deliberately mode-agnostic — a danger
    # red stays a danger red — so these have no `_dark` twin, and
    # dark_mode.scss keeps its own lifted variants for contrast on the
    # dark canvas until an admin overrides them here.
    theme_color_info = fields.Char(
        string="Info", default="#0284c7",
        config_parameter="bluenova_backend_theme.color_info")
    theme_color_success = fields.Char(
        string="Success", default="#16a34a",
        config_parameter="bluenova_backend_theme.color_success")
    theme_color_warning = fields.Char(
        string="Warning", default="#d97706",
        config_parameter="bluenova_backend_theme.color_warning")
    theme_color_danger = fields.Char(
        string="Danger", default="#ef4444",
        config_parameter="bluenova_backend_theme.color_danger")

    # ── Authentication pages ─────────────────────────────────────
    # The login, signup and reset-password screens render through
    # web.assets_frontend, a separate bundle from the backend one, but
    # they read the same --cmt-* tokens. Only the surfaces that would
    # look wrong inheriting a backend colour get their own pickers.
    #
    # Every field here is paired with a `_dark` twin below. The pair
    # writes the same CSS token under opposite selectors — see
    # _THEME_CSS_VARS_DARK.
    theme_color_login_bg = fields.Char(
        string="Login Background", default="#f8f9fa",
        config_parameter="bluenova_backend_theme.color_login_bg")
    theme_color_login_card_bg = fields.Char(
        string="Login Panel Background", default="#ffffff",
        config_parameter="bluenova_backend_theme.color_login_card_bg")
    theme_color_auth_action_bg = fields.Char(
        string="Login Button Background", default="#1e3a8a",
        config_parameter="bluenova_backend_theme.color_auth_action_bg")
    theme_color_auth_action_text = fields.Char(
        string="Login Button Text", default="#ffffff",
        config_parameter="bluenova_backend_theme.color_auth_action_text")

    theme_color_login_bg_dark = fields.Char(
        string="Login Background (Dark)", default="#0b1120",
        config_parameter="bluenova_backend_theme.color_login_bg_dark")
    theme_color_login_card_bg_dark = fields.Char(
        string="Login Panel Background (Dark)", default="#131c31",
        config_parameter="bluenova_backend_theme.color_login_card_bg_dark")
    theme_color_auth_action_bg_dark = fields.Char(
        string="Login Button Background (Dark)", default="#1e3a8a",
        config_parameter="bluenova_backend_theme.color_auth_action_bg_dark")
    theme_color_auth_action_text_dark = fields.Char(
        string="Login Button Text (Dark)", default="#ffffff",
        config_parameter="bluenova_backend_theme.color_auth_action_text_dark")

    theme_login_background_image_dark = fields.Binary(
        string="Login Background Image (Dark)")

    # ── Home page ────────────────────────────────────────────────
    # The two lines of the public hero — headline and standfirst — each
    # get their own colour rather than borrowing the canvas text tokens,
    # so the hero can be tuned without moving every other surface.
    theme_color_home_title = fields.Char(
        string="Home Title", default="#111827",
        config_parameter="bluenova_backend_theme.color_home_title")
    theme_color_home_lead = fields.Char(
        string="Home Lead", default="#4b5563",
        config_parameter="bluenova_backend_theme.color_home_lead")

    theme_color_home_title_dark = fields.Char(
        string="Home Title (Dark)", default="#f8fafc",
        config_parameter="bluenova_backend_theme.color_home_title_dark")
    theme_color_home_lead_dark = fields.Char(
        string="Home Lead (Dark)", default="#94a3b8",
        config_parameter="bluenova_backend_theme.color_home_lead_dark")

    # ── Hero typography ──────────────────────────────────────────
    # Integers, not Chars: the settings screen gets a number input, the
    # ORM rejects "60px" before it reaches the stylesheet, and the unit
    # is added on the way out by _THEME_METRIC_VARS. Shared by both
    # colour schemes — a type scale is not a palette.
    theme_home_title_size = fields.Integer(
        string="Title Size (px)", default=59,
        config_parameter="bluenova_backend_theme.home_title_size")
    theme_home_title_weight = fields.Integer(
        string="Title Weight", default=800,
        config_parameter="bluenova_backend_theme.home_title_weight")
    theme_home_lead_size = fields.Integer(
        string="Lead Size (px)", default=15,
        config_parameter="bluenova_backend_theme.home_lead_size")
    theme_home_lead_weight = fields.Integer(
        string="Lead Weight", default=500,
        config_parameter="bluenova_backend_theme.home_lead_weight")

    # Opt-in, and it has to be: ir.config_parameter.set_param deletes the
    # row when handed False, so a Boolean config_parameter defaulting to
    # True can never be switched off — get_values would read the deleted
    # key, fall back to the default and tick the box straight back on.
    # Every flag on this screen is therefore default-False.
    theme_login_use_brand_image = fields.Boolean(
        string="Use Brand Image As Login Logo",
        config_parameter="bluenova_backend_theme.login_use_brand_image")
    theme_login_tagline = fields.Char(
        string="Login Tagline",
        config_parameter="bluenova_backend_theme.login_tagline")

    # Same reasoning as the sidebar image above: an attachment, not an
    # ir.config_parameter row.
    theme_login_background_image = fields.Binary(
        string="Login Background Image")

    # ── Landing & public pages ───────────────────────────────────
    theme_landing_dashboard = fields.Boolean(
        string="Open Dashboard After Login",
        config_parameter="bluenova_backend_theme.landing_dashboard")
    theme_public_home_enabled = fields.Boolean(
        string="Themed Public Home Page",
        config_parameter="bluenova_backend_theme.public_home_enabled")

    # ─────────────────────────────────────────────────────────────
    # Persistence
    #
    # The colour fields carry `config_parameter`, so res.config.settings
    # reads and writes them on its own — including falling back to the
    # field's `default` when the parameter is absent, which is what makes
    # Reset (below) work by simply clearing the parameters. Only the
    # image needs hand-written get/set.
    # ─────────────────────────────────────────────────────────────

    @api.model
    def get_values(self):
        res = super().get_values()
        for fname, name in self._IMAGE_ATTACHMENTS.items():
            attachment = self._get_theme_attachment(name)
            res[fname] = attachment.datas if attachment else False
        return res

    def set_values(self):
        # Reject bad colours before anything is written, so a rejected
        # save leaves the stored theme exactly as it was rather than
        # half-applied.
        for fname in self._all_color_fields():
            value = (self[fname] or "").strip()
            if value and not COLOR_RE.match(value):
                raise UserError(_(
                    "%(label)s is not a valid colour: %(value)r\n\n"
                    "Use a hex code (#3959b0) or an rgb()/rgba() value.",
                    label=self._fields[fname].string, value=value,
                ))
        # Same idea for the numbers. 0 is what an emptied input gives,
        # and it means "unset" — set_values deletes the parameter and
        # the field default takes over — so it is allowed through rather
        # than reported as out of range.
        for fname, (_var, _unit, bounds_key) in self._THEME_METRIC_VARS.items():
            value = self[fname]
            low, high = METRIC_BOUNDS[bounds_key]
            if value and not low <= value <= high:
                raise UserError(_(
                    "%(label)s must be between %(low)s and %(high)s.",
                    label=self._fields[fname].string, low=low, high=high,
                ))
        super().set_values()
        for fname, name in self._IMAGE_ATTACHMENTS.items():
            self._set_theme_attachment(name, self[fname])

    # ── Uploaded images ──────────────────────────────────────────
    # Binary field → attachment name. Both images are handled by the
    # same pair of helpers below rather than one get/set per picture.

    _IMAGE_ATTACHMENTS = {
        "theme_sidebar_brand_image": BRAND_IMAGE_NAME,
        "theme_login_background_image": LOGIN_BG_IMAGE_NAME,
        "theme_login_background_image_dark": LOGIN_BG_IMAGE_DARK_NAME,
    }

    @api.model
    def _all_color_fields(self):
        """Every field validated as a colour, light and dark.

        One place, so a new map can never be added to the screen and
        silently skip validation — which would put an unchecked string
        one hop away from a <style> block.
        """
        return list(self._THEME_CSS_VARS) + list(self._THEME_CSS_VARS_DARK)

    @api.model
    def _get_theme_attachment(self, name):
        return self.env["ir.attachment"].sudo().search(
            [("name", "=", name)], limit=1)

    def _set_theme_attachment(self, name, datas):
        """Store (or clear) one of the theme's images as a single attachment."""
        attachment = self._get_theme_attachment(name)
        if not datas:
            attachment.unlink()
            return
        values = {
            "name": name,
            "type": "binary",
            "datas": datas,
            # Served to the browser through /web/image by
            # views/theme_styles.xml and views/auth_theme.xml. The
            # attachment has no res_model, so ir.attachment's record rule
            # would otherwise let only its creator read it — every other
            # user would get a broken image, and on the login page there
            # is no user at all.
            "public": True,
        }
        if attachment:
            attachment.write(values)
        else:
            self.env["ir.attachment"].sudo().create(values)

    @api.model
    def _theme_image_url(self, name):
        """Cache-busting /web/image URL for a theme image, or False.

        `unique` busts the browser cache when the image is replaced;
        without it a new upload keeps showing the old picture.
        """
        attachment = self._get_theme_attachment(name)
        if not attachment:
            return False
        stamp = fields.Datetime.to_string(
            attachment.write_date or attachment.create_date)
        return "/web/image/%s?unique=%s" % (
            attachment.id,
            stamp.replace(" ", "").replace(":", "").replace("-", ""),
        )

    # ─────────────────────────────────────────────────────────────
    # Runtime CSS
    #
    # Every method below returns Markup, not str. On 14 the templates
    # rendered these with t-raw; t-raw was removed in 15.0 and t-out is
    # its replacement — but t-out escapes anything that is not already
    # Markup, and an escaped stylesheet is a broken one (`url('…')`
    # becomes `url(&#39;…&#39;)`). Marking the string safe here rather
    # than in the templates keeps the decision next to the validation
    # that justifies it: every value interpolated below has been through
    # COLOR_RE or an integer range check, and the property names come
    # from this module's own maps.
    # ─────────────────────────────────────────────────────────────

    @api.model
    def _get_theme_css(self):
        """Return the <style> body that applies the stored light theme.

        Rendered into the backend page head by views/theme_styles.xml,
        and into the login and public pages by views/auth_theme.xml and
        views/public_home.xml — those render through web.frontend_layout,
        a different bundle that never loads web.webclient_bootstrap, so
        they need their own copy of the same block. A save repaints all
        of them on the next page load with no asset-bundle rebuild and no
        server restart.

        Scoped to `:root:not([data-cmt-theme="dark"])` on purpose. These
        are the light-mode colours (the settings screen says as much);
        the dark scheme belongs to _get_theme_css_dark() and, in the
        backend, to scss/dark_mode.scss — either of whose
        `:root[data-cmt-theme="dark"]` blocks would otherwise be beaten
        by a bare `:root` rule arriving later in the document.
        """
        return self._render_theme_css(
            ':root:not([data-cmt-theme="dark"])',
            self._THEME_CSS_VARS,
            (
                ("--cmt-sidebar-brand-image", BRAND_IMAGE_NAME),
                ("--cmt-login-bg-image", LOGIN_BG_IMAGE_NAME),
            ),
        )

    @api.model
    def _get_theme_css_dark(self):
        """Dark-mode counterpart of _get_theme_css().

        Scoped to `:root[data-cmt-theme="dark"]` — the exact opposite
        selector — so it applies only once js/theme_mode.js has set that
        attribute on <html>, and the two blocks can never both match.
        Neither has to outrank the other.

        Emitted after the light block by every template that renders
        both, so at equal specificity the dark rules also win on
        document order once their selector matches.

        The sidebar brand image is repeated here deliberately: it is a
        picture, not a colour, and it does not change with the scheme —
        but the light block that carries it stops matching in dark mode,
        so without this line the sidebar would lose its artwork the
        moment someone flipped the switch.
        """
        color_vars = dict(self._THEME_CSS_VARS_DARK)
        color_vars.update({
            fname: self._THEME_CSS_VARS[fname]
            for fname in self._THEME_SHARED_COLOR_FIELDS
        })
        return self._render_theme_css(
            ':root[data-cmt-theme="dark"]',
            color_vars,
            (
                ("--cmt-sidebar-brand-image", BRAND_IMAGE_NAME),
                ("--cmt-login-bg-image", LOGIN_BG_IMAGE_DARK_NAME),
            ),
        )

    @api.model
    def _get_theme_metrics_css(self):
        """The hero type scale, on a bare `:root`.

        Neither of the two blocks above can carry these. The light block
        is scoped `:not([data-cmt-theme="dark"])`, so the hero would
        lose its sizing the moment dark mode came on; the dark block has
        the mirror-image problem. A type scale is not part of a palette
        and does not belong to either scheme.

        `:root` here and `:root` in variables.scss are the same
        specificity, so this wins purely on document order — which holds
        because every template that renders it puts the <style> after
        the compiled bundle.
        """
        icp = self.env["ir.config_parameter"].sudo()
        declarations = []

        for fname, (css_var, unit, bounds_key) in self._THEME_METRIC_VARS.items():
            raw = (icp.get_param(self._fields[fname].config_parameter) or "").strip()
            if not raw:
                continue
            # Re-validated on the way out for the same reason the
            # colours are: nothing guarantees this row came through
            # set_values() rather than a shell session or a data file.
            try:
                value = int(raw)
            except ValueError:
                _logger.warning(
                    "Ignoring non-numeric %r stored in %s", raw,
                    self._fields[fname].config_parameter)
                continue
            low, high = METRIC_BOUNDS[bounds_key]
            if not low <= value <= high:
                _logger.warning(
                    "Ignoring out-of-range %s=%s (expected %s..%s)",
                    self._fields[fname].config_parameter, value, low, high)
                continue
            declarations.append("    %s: %s%s;" % (css_var, value, unit))

        if not declarations:
            return ""
        return Markup(":root {\n%s\n}" % "\n".join(declarations))

    @api.model
    def _render_theme_css(self, selector, color_vars, image_vars):
        """Body shared by the light and dark emitters above.

        One implementation, two callers: the only differences between
        the two blocks are the selector, which field map is read, and
        which attachments supply the images. Duplicating the loop would
        mean the validation below has to be remembered twice.

        :param str selector: CSS selector the declarations are scoped to
        :param dict color_vars: field name → CSS custom property
        :param image_vars: iterable of (CSS custom property, attachment name)
        :returns: Markup, or "" when nothing has been customised
        """
        icp = self.env["ir.config_parameter"].sudo()
        declarations = []

        for fname, css_var in color_vars.items():
            param = self._fields[fname].config_parameter
            value = (icp.get_param(param) or "").strip()
            # Unset means "use the compiled default", which the alias in
            # variables.scss (light) or the stylesheet's own dark block
            # already provides — so emit nothing rather than re-stating
            # it here in a second place.
            if not value:
                continue
            # Re-checked on the way out, not just on the way in: a value
            # could have been written straight to ir.config_parameter by
            # another module, a data file, or a shell session, none of
            # which pass through set_values().
            if not COLOR_RE.match(value):
                _logger.warning(
                    "Ignoring invalid colour %r stored in %s", value, param)
                continue
            declarations.append("    %s: %s;" % (css_var, value))

        for css_var, name in image_vars:
            url = self._theme_image_url(name)
            if url:
                declarations.append("    %s: url('%s');" % (css_var, url))

        if not declarations:
            return ""
        return Markup("%s {\n%s\n}" % (selector, "\n".join(declarations)))

    # ─────────────────────────────────────────────────────────────
    # Presets: export / import / reset
    # ─────────────────────────────────────────────────────────────

    def action_export_theme_settings(self):
        """Download the current colours as a JSON preset.

        Both schemes: a preset that carried only the light colours would
        restore half a theme, and the omission would not be visible
        until someone switched to dark.

        Colours only — the images are deliberately left out, matching
        the note on the settings screen. A preset stays a small text file
        that can be diffed and committed.
        """
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        payload = {
            "_module": "bluenova_backend_theme",
            "_version": 1,
            "colors": {
                fname: (icp.get_param(self._fields[fname].config_parameter) or "")
                for fname in self._all_color_fields()
            },
            # Separate key, not folded into "colors": the import wizard
            # runs COLOR_RE over everything under "colors", and a type
            # scale is not a colour. A preset written before this key
            # existed simply has no "metrics" entry, which the wizard
            # reads as "unset them", exactly as it already treats a
            # missing colour.
            "metrics": {
                fname: (icp.get_param(self._fields[fname].config_parameter) or "")
                for fname in self._THEME_METRIC_VARS
            },
        }
        attachment = self.env["ir.attachment"].create({
            "name": "bluenova_theme_settings.json",
            "type": "binary",
            "mimetype": "application/json",
            "datas": base64.b64encode(
                json.dumps(payload, indent=2, sort_keys=True).encode()),
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }

    def action_import_theme_settings(self):
        """Open the file picker that applies a preset."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Import Theme Settings"),
            "res_model": "bluenova.theme.import.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def action_reset_theme_settings(self):
        """Drop every stored colour and the brand image.

        Clearing the parameter is all that is needed: get_values() falls
        back to each field's `default`, and _get_theme_css() emits no
        declaration for an unset value, so the page goes back to the
        colours compiled into the stylesheets.
        """
        icp = self.env["ir.config_parameter"].sudo()
        names = (self._all_color_fields()
                 + list(self._THEME_METRIC_VARS)
                 + list(self._THEME_FLAG_PARAMS))
        for fname in names:
            param = icp.search(
                [("key", "=", self._fields[fname].config_parameter)])
            param.unlink()
        for name in self._IMAGE_ATTACHMENTS.values():
            self._get_theme_attachment(name).unlink()
        return {"type": "ir.actions.client", "tag": "reload"}

    # ─────────────────────────────────────────────────────────────
    # Auth / public page branding
    # ─────────────────────────────────────────────────────────────

    @api.model
    def _get_auth_branding(self):
        """Logo and tagline for the login, signup and reset-password pages.

        One call rather than three, because views/auth_theme.xml renders
        on an unauthenticated request: every lookup there runs as sudo on
        a public session, so the fewer of them the better.

        `logo_url` is False unless the admin has both uploaded a brand
        image and opted into using it here — the template then keeps
        Odoo's own /web/binary/company_logo, so an untouched install
        looks exactly as it did before this feature existed.
        """
        icp = self.env["ir.config_parameter"].sudo()
        # A Boolean config_parameter is stored as the string "True", and
        # its row is deleted rather than set to "False" when unticked
        # (see the field's comment), so anything that is not "True" is
        # off.
        enabled = icp.get_param(
            "bluenova_backend_theme.login_use_brand_image") == "True"
        return {
            "logo_url": self._theme_image_url(BRAND_IMAGE_NAME) if enabled else False,
            "tagline": (icp.get_param(
                "bluenova_backend_theme.login_tagline") or "").strip(),
        }
