import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

ICON_ROOT = "/bluenova_backend_theme/static/src/image/icons/"


class ThemeDashboard(models.AbstractModel):
    """Data behind the themed landing dashboard.

    An AbstractModel on purpose: the dashboard stores nothing, so there
    is no table to create and no row to add to
    security/ir.model.access.csv — an ACL only exists for models that
    have records, and adding one here would be a permission on nothing.

    The theme depends on `web` and `base_setup` only, so none of the
    models below are guaranteed to exist. Each tile is therefore built
    behind two guards, and a tile that fails either one is dropped
    silently rather than rendered empty:

      • the model is installed at all (`model in self.env`)
      • the user may read it (`has_access`, non-raising)

    That second guard is what keeps the dashboard honest: counts are
    read as the *current user*, never sudo, so a salesperson's tile and
    an accountant's tile show the numbers each of them is allowed to
    see, and record rules apply exactly as they do in the list view the
    tile links to.
    """

    _name = "bluenova.theme.dashboard"
    _description = "BlueNova Theme Dashboard"

    # Model → tile definition. `action` is resolved through env.ref with
    # raise_if_not_found, so a renamed or missing action costs the tile
    # its click target, not the whole dashboard.
    #
    # Every domain here is deliberately the "needs attention" slice
    # rather than a grand total: a number that never changes is not
    # worth a card.
    _TILES = [
        {
            "key": "crm",
            "model": "crm.lead",
            "label": "Opportunities",
            "sub": "Open pipeline",
            "icon": "crm.png",
            "domain": [("type", "=", "opportunity")],
            "action": "crm.crm_lead_action_pipeline",
        },
        {
            "key": "sale",
            "model": "sale.order",
            "label": "Quotations",
            "sub": "Awaiting confirmation",
            "icon": "sales.png",
            "domain": [("state", "in", ("draft", "sent"))],
            "action": "sale.action_quotations_with_onboarding",
        },
        {
            "key": "purchase",
            "model": "purchase.order",
            "label": "Requests For Quotation",
            "sub": "Not yet ordered",
            "icon": "purchase.png",
            "domain": [("state", "in", ("draft", "sent"))],
            "action": "purchase.purchase_rfq",
        },
        {
            "key": "account",
            "model": "account.move",
            "label": "Customer Invoices",
            "sub": "Posted",
            "icon": "invoice.png",
            "domain": [("move_type", "=", "out_invoice"), ("state", "=", "posted")],
            "action": "account.action_move_out_invoice_type",
        },
        {
            "key": "project",
            "model": "project.task",
            "label": "Tasks",
            "sub": "Still open",
            "icon": "project.png",
            # stage_id.fold is how Odoo itself marks a stage as closed,
            # so this follows whatever the project manager configured
            # rather than hardcoding stage names.
            "domain": [("stage_id.fold", "=", False)],
            "action": "project.action_view_task",
        },
        {
            "key": "stock",
            "model": "stock.picking",
            "label": "Transfers",
            "sub": "To process",
            "icon": "inventory.png",
            "domain": [("state", "in", ("assigned", "confirmed", "waiting"))],
            "action": "stock.action_picking_tree_ready",
        },
        {
            "key": "hr",
            "model": "hr.employee",
            "label": "Employees",
            "sub": "Currently active",
            "icon": "employee.png",
            "domain": [],
            "action": "hr.open_view_employee_list_my",
        },
    ]

    @api.model
    def get_dashboard_data(self):
        """Return the tiles this user can actually see.

        Called once by static/src/js/home_dashboard.js when the client
        action opens. One RPC for the whole dashboard rather than one
        per tile.
        """
        tiles = []
        for spec in self._TILES:
            tile = self._build_tile(spec)
            if tile:
                tiles.append(tile)

        return {
            "tiles": tiles,
            "user_name": self.env.user.name,
            "company_name": self.env.company.name,
        }

    def _build_tile(self, spec):
        """One tile, or None when it does not apply to this user."""
        model = spec["model"]
        if model not in self.env:
            return None

        records = self.env[model]
        # `check_access_rights(op, raise_exception=False)` was deprecated
        # in 18.0 and is the non-raising half of `has_access` in 19.0.
        if not records.has_access("read"):
            return None

        try:
            count = records.search_count(spec["domain"])
        except Exception:
            # A domain can still fail on an installed model — a field
            # renamed by another module, a record rule that references
            # something this user cannot resolve. One broken tile must
            # not take the page down, so it is logged and dropped.
            _logger.warning(
                "Skipping dashboard tile %r: count failed", spec["key"],
                exc_info=True)
            return None

        action = self.env.ref(spec["action"], raise_if_not_found=False)

        return {
            "key": spec["key"],
            "label": spec["label"],
            "sub": spec["sub"],
            "value": count,
            "icon": ICON_ROOT + spec["icon"],
            "action_id": action.id if action else False,
        }
