import logging

from odoo import http
from odoo.http import request

# Odoo 19: web's Home controller lives in controllers/home.py. It was split
# out of controllers/main.py in 16.0, so the 14.0 import path
# (`odoo.addons.web.controllers.main`) no longer resolves.
from odoo.addons.web.controllers.home import Home

_logger = logging.getLogger(__name__)

DASHBOARD_ACTION = "bluenova_backend_theme.action_home_dashboard"
PUBLIC_HOME_TEMPLATE = "bluenova_backend_theme.public_home"

# Where an internal user lands when nothing else has a claim on the
# redirect. `/web` on 14; `/odoo` since 17.0 — see
# odoo/addons/web/controllers/utils.py::_get_login_redirect_url.
DEFAULT_LANDING_URL = "/odoo"


class BlueNovaHome(Home):
    """Two hooks on web's own Home controller.

    Both are opt-in and both fall through to the original behaviour when
    their setting is off, so installing the theme changes neither where
    login lands nor what `/` serves until an admin says so.
    """

    def _login_redirect(self, uid, redirect=None):
        """Land on the themed dashboard after login, when configured.

        Not a route — this is the plain method web's own `web_login`
        calls once authentication has succeeded, which is why it is the
        right hook: it runs after 2FA and after the session is
        established, not instead of them.

        The override is written as "only rewrite the default": super()
        returns '/odoo' exactly when nothing else has a claim on where
        the user goes. Anything else it returns — an explicit ?redirect=
        from a deep link the user was bounced off, the
        '/web/login_successful' page a portal user gets, or the
        interstitial an auth_totp-style module needs — is passed through
        untouched.
        """
        url = super()._login_redirect(uid, redirect=redirect)
        if url != DEFAULT_LANDING_URL:
            return url

        # Booleans on the settings screen are stored as the string
        # "True", and their row is deleted rather than written "False"
        # when unticked (ir.config_parameter.set_param), so anything that
        # is not exactly "True" means off.
        icp = request.env["ir.config_parameter"].sudo()
        if icp.get_param("bluenova_backend_theme.landing_dashboard") != "True":
            return url

        action = request.env.ref(DASHBOARD_ACTION, raise_if_not_found=False)
        if not action:
            # The module is installed but its action is gone — a partial
            # upgrade, or the record deleted by hand. Falling back to the
            # normal landing page is strictly better than a URL that
            # opens an "Undefined action" dialog.
            _logger.warning(
                "Landing dashboard is enabled but %s could not be resolved",
                DASHBOARD_ACTION)
            return url

        # Odoo 19 routes the web client on real paths rather than on the
        # hash fragment: `/odoo/action-<id>`, not `/web#action=<id>`.
        return "/odoo/action-%s" % action.id

    @http.route()
    def index(self, s_action=None, db=None, **kw):
        """Serve the themed public page at `/`, when configured.

        Bare `@http.route()` re-uses the parent's routing (`/`, type
        http, auth none) rather than declaring a second one.

        Four conditions have to hold before this takes over, and the
        order matters:

          1. a database is resolved at all — `/` is reachable before
             ensure_db() has ever run, and `request.env` needs a cursor;
          2. nobody is logged in — a signed-in user hitting `/` still
             wants the web client, which is what super() gives them;
          3. the admin turned the page on (it ships off, because
             silently changing what `/` does on a running instance is
             not a theming decision);
          4. `website` is not installed. That module owns `/` properly,
             with an editable page behind it; a backend theme has no
             business winning that fight, so it stands down.
        """
        if not request.db or request.session.uid:
            return super().index(s_action=s_action, db=db, **kw)

        icp = request.env["ir.config_parameter"].sudo()
        enabled = icp.get_param(
            "bluenova_backend_theme.public_home_enabled") == "True"
        if not enabled or "website" in request.env:
            return super().index(s_action=s_action, db=db, **kw)

        # There is no user on this request, so there is no env.company to
        # read: the oldest company is the instance's own, the same one
        # /web/binary/company_logo falls back to.
        company = request.env["res.company"].sudo().search(
            [], order="id", limit=1)
        branding = request.env["res.config.settings"].sudo()._get_auth_branding()
        return request.render(PUBLIC_HOME_TEMPLATE, {
            "cmt_branding": branding,
            "cmt_company": company,
        })
