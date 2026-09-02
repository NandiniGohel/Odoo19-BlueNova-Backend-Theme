import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

ICON_ROOT = "/bluenova_backend_theme/static/src/image/icons/"

# How many days the sparkline on a metric card covers. Seven is a week,
# so the shape reads against the weekend dip a business rhythm has.
SPARK_DAYS = 7

# The trend line under a hero card compares the last 30 days against the
# 30 before them. Not a calendar month on purpose: "vs last month" on
# the 2nd would compare one day against thirty.
TREND_WINDOW = 30

# The chart panel covers the same 30 days, one bar per day. Deliberately
# TREND_WINDOW and not a window of its own: the chart and the "+12% vs
# previous 30 days" line under a hero card then describe the same
# period, so a reader comparing them is comparing like with like.
CHART_WINDOW = TREND_WINDOW

# How many series the chart's selector offers. Each one is another
# grouped query on page load, and a strip of eight chips over a chart is
# a menu rather than a control.
CHART_SERIES = 4


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

    ── Shape of the payload ─────────────────────────────────────

    The layout in screen.png is five regions, so `get_dashboard_data`
    returns one key per region rather than one flat list: the regions
    are not interchangeable — a hero card carries a trend line, a metric
    card carries a sparkline or a pair of pills, and the two are sized
    differently in the grid. Deciding which tile is which client-side
    would mean the JS knowing the order of `_TILES`, which is a server
    concern.

      heroes        the two largest figures, on gradient cards
      tiles         the remaining figures, as plain metric cards
      chart         a day-by-day series per app, for the trend panel
      activity      the newest records across everything readable
      quick_actions "create a…" shortcuts, one per creatable model
      preview       a short list of the user's own open work

    Every region degrades to empty independently. A database with only
    `web` installed gets the greeting and nothing else, which is what
    the empty state is for.
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
    #
    # `singular` is the noun used in the activity feed ("New quotation:
    # S00042") and on the quick-action buttons ("New Quotation"), where
    # the plural card label would not read. It is a separate string, not
    # a naive de-pluralisation of `label`: "Requests For Quotation" and
    # "Employees" do not depluralise the same way.
    #
    # `pills` is model-specific detail rendered under the figure — a
    # domain per pill, counted the same guarded way as the tile itself.
    #
    # `history` is the domain to use when counting *by creation date*
    # rather than counting what is open now — the hero trend, the
    # sparkline and the chart. It exists because `domain` above is the
    # needs-attention slice, and a needs-attention slice cannot be read
    # backwards in time: a quotation created five weeks ago and
    # confirmed since is no longer draft, so it silently drops out of
    # every historical bucket it belonged to. Counting a *history*
    # against `domain` therefore does not just lose records, it loses
    # them in proportion to their age — the further back the bucket, the
    # more of it has been closed — which bends every one of those
    # readings the same way: charts that sag towards the left and a
    # trend line that reports growth on a database where nothing
    # changed.
    #
    # So `history` keeps only the clauses that say what *kind* of record
    # this is ("opportunities, not leads") and drops the ones that say
    # what state it is in today. A spec whose domain is already
    # state-free needs no entry and falls back to `domain`.
    _TILES = [
        {
            "key": "crm",
            "model": "crm.lead",
            "label": "Opportunities",
            "singular": "opportunity",
            "sub": "Open pipeline",
            "icon": "crm.png",
            "domain": [("type", "=", "opportunity")],
            "action": "crm.crm_lead_action_pipeline",
        },
        {
            "key": "sale",
            "model": "sale.order",
            "label": "Quotations",
            "singular": "quotation",
            "sub": "Awaiting confirmation",
            "icon": "sales.png",
            "domain": [("state", "in", ("draft", "sent"))],
            # A confirmed order was still a quotation when it was
            # created, and the day it was created is what the series is
            # counting.
            "history": [],
            "action": "sale.action_quotations_with_onboarding",
        },
        {
            "key": "purchase",
            "model": "purchase.order",
            "label": "Requests For Quotation",
            "singular": "request for quotation",
            "sub": "Not yet ordered",
            "icon": "purchase.png",
            "domain": [("state", "in", ("draft", "sent"))],
            "history": [],
            "action": "purchase.purchase_rfq",
        },
        {
            "key": "account",
            "model": "account.move",
            "label": "Customer Invoices",
            "singular": "invoice",
            "sub": "Posted",
            "icon": "invoice.png",
            "domain": [("move_type", "=", "out_invoice"), ("state", "=", "posted")],
            # move_type is what the record *is*; state is where it has
            # got to. Only the first half survives into the history.
            "history": [("move_type", "=", "out_invoice")],
            "action": "account.action_move_out_invoice_type",
        },
        {
            "key": "project",
            "model": "project.task",
            "label": "Tasks",
            "singular": "task",
            "sub": "Still open",
            "icon": "project.png",
            # stage_id.fold is how Odoo itself marks a stage as closed,
            # so this follows whatever the project manager configured
            # rather than hardcoding stage names.
            "domain": [("stage_id.fold", "=", False)],
            # Every task ever closed would otherwise disappear out of
            # the week it was opened in.
            "history": [],
            "action": "project.action_view_task",
        },
        {
            "key": "stock",
            "model": "stock.picking",
            "label": "Transfers",
            "singular": "transfer",
            "sub": "To process",
            "icon": "inventory.png",
            "domain": [("state", "in", ("assigned", "confirmed", "waiting"))],
            "history": [],
            "action": "stock.action_picking_tree_ready",
            # The in/out split under the figure, as in screen.png's
            # "12 IN / 6 OUT". picking_type_id.code is the field Odoo's
            # own Inventory overview groups on.
            "pills": [
                {
                    "label": "IN",
                    "dir": "in",
                    "domain": [("picking_type_id.code", "=", "incoming")],
                },
                {
                    "label": "OUT",
                    "dir": "out",
                    "domain": [("picking_type_id.code", "=", "outgoing")],
                },
            ],
        },
        {
            "key": "hr",
            "model": "hr.employee",
            "label": "Employees",
            "singular": "employee",
            "sub": "Currently active",
            "icon": "employee.png",
            "domain": [],
            "action": "hr.open_view_employee_list_my",
        },
    ]

    # The preview panel, in preference order: the first candidate whose
    # model is installed, readable and non-empty wins and the rest are
    # not considered. Ordered by how personal the list is — a user's own
    # tasks say more about their day than the company's open invoices —
    # and `domain` is a callable because "mine" has to be resolved
    # against the current user at call time, not at import time.
    _PREVIEW_SOURCES = [
        {
            "model": "project.task",
            "title": "Tasks Preview",
            "action": "project.action_view_task",
            "domain": lambda self: [
                ("stage_id.fold", "=", False),
                ("user_ids", "in", self.env.user.id),
            ],
            "sub_field": "project_id",
        },
        {
            "model": "crm.lead",
            "title": "My Pipeline",
            "action": "crm.crm_lead_action_pipeline",
            "domain": lambda self: [
                ("type", "=", "opportunity"),
                ("user_id", "=", self.env.user.id),
            ],
            "sub_field": "stage_id",
        },
        {
            "model": "sale.order",
            "title": "My Quotations",
            "action": "sale.action_quotations_with_onboarding",
            "domain": lambda self: [
                ("state", "in", ("draft", "sent")),
                ("user_id", "=", self.env.user.id),
            ],
            "sub_field": "partner_id",
        },
    ]

    # ────────────────────────────────────────────────────────────
    # Entry point
    # ────────────────────────────────────────────────────────────

    @api.model
    def get_dashboard_data(self):
        """Return every region of the dashboard this user can see.

        Called once by static/src/js/home_dashboard.js when the client
        action opens. One RPC for the whole dashboard rather than one
        per region.
        """
        tiles = []
        for spec in self._TILES:
            tile = self._build_tile(spec)
            if tile:
                tiles.append(tile)

        # Records created per day, per model — one grouped query each,
        # and the only place they are run. The sparkline under a metric
        # card is the last seven days of the same thirty the chart
        # plots, so counting the two separately would be two queries per
        # app for one set of numbers.
        history = {
            tile["key"]: self._daily_counts(tile["_spec"], CHART_WINDOW)
            for tile in tiles
        }

        # The two biggest figures lead the page. Sorted by value rather
        # than taken off the front of _TILES, so the hero cards are the
        # numbers that actually dominate this database — an
        # Inventory-only install should not lead with an empty CRM card.
        heroes = sorted(tiles, key=lambda tile: tile["value"], reverse=True)[:2]
        hero_keys = {tile["key"] for tile in heroes}
        for hero in heroes:
            hero["trend"] = self._trend(hero["_spec"])

        rest = [tile for tile in tiles if tile["key"] not in hero_keys]
        for tile in rest:
            tile["spark"] = self._spark(history[tile["key"]])

        # `_spec` is the server-side definition, carried on the dict only
        # so the enrichment above can reach the model and its domain. It
        # has no business crossing the RPC boundary.
        for tile in tiles:
            tile.pop("_spec", None)

        return {
            "heroes": heroes,
            "tiles": rest,
            "chart": self._build_chart(tiles, history),
            "activity": self._build_activity(),
            "quick_actions": self._build_quick_actions(),
            "preview": self._build_preview(),
            "user_name": self.env.user.name,
            "company_name": self.env.company.name,
        }

    # ────────────────────────────────────────────────────────────
    # Tiles
    # ────────────────────────────────────────────────────────────

    def _records(self, spec):
        """The model behind a spec, or None when it is unusable here.

        The two guards from the class docstring, in one place, so every
        region below asks the same question the same way.
        """
        model = spec["model"]
        if model not in self.env:
            return None

        records = self.env[model]
        # `check_access_rights(op, raise_exception=False)` was deprecated
        # in 18.0 and is the non-raising half of `has_access` in 19.0.
        if not records.has_access("read"):
            return None
        return records

    def _history_domain(self, spec):
        """The domain to count a spec's *history* against.

        See the note on `history` in _TILES: the tile's own domain
        describes what needs attention today and cannot be read
        backwards through time without bending the series. Anything
        counted per creation date asks for this one instead.
        """
        return spec.get("history", spec["domain"])

    def _build_tile(self, spec):
        """One tile, or None when it does not apply to this user."""
        records = self._records(spec)
        if records is None:
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
            "pills": self._build_pills(spec, records),
            # Enrichment handle; stripped before the payload is returned.
            "_spec": spec,
        }

    def _build_pills(self, spec, records):
        """The IN/OUT style breakdown under a figure, if the spec has one."""
        pills = []
        for pill in spec.get("pills", []):
            try:
                count = records.search_count(spec["domain"] + pill["domain"])
            except Exception:
                _logger.warning(
                    "Skipping dashboard pill %r/%r", spec["key"], pill["label"],
                    exc_info=True)
                continue
            pills.append({
                "label": pill["label"],
                "dir": pill["dir"],
                "value": count,
            })
        return pills

    def _trend(self, spec):
        """Percentage change over the last TREND_WINDOW days, or None.

        None rather than zero when there is no baseline to compare
        against: a fresh database would otherwise announce "+0.0% vs
        previous 30 days" under every hero card, which is a claim about
        data that does not exist.

        Counted against the history domain, not the tile's. This is the
        reading the distinction was introduced for: with the tile's
        needs-attention domain, the older of the two windows has had a
        further thirty days for its records to be confirmed, closed or
        validated out of it, so it comes back systematically emptier
        than the recent one and the card reports growth on a database
        where nothing has changed at all.
        """
        records = self._records(spec)
        if records is None or "create_date" not in records._fields:
            return None

        domain = self._history_domain(spec)
        now = fields.Datetime.now()
        current_start = now - timedelta(days=TREND_WINDOW)
        previous_start = now - timedelta(days=TREND_WINDOW * 2)

        try:
            current = records.search_count(
                domain + [("create_date", ">=", current_start)])
            previous = records.search_count(
                domain + [
                    ("create_date", ">=", previous_start),
                    ("create_date", "<", current_start),
                ])
        except Exception:
            _logger.warning(
                "Skipping dashboard trend %r", spec["key"], exc_info=True)
            return None

        if not previous:
            return None

        pct = (current - previous) * 100.0 / previous
        return {
            "dir": "up" if pct >= 0 else "down",
            "text": _(
                "%(pct)+.1f%% vs previous %(days)s days",
                pct=pct, days=TREND_WINDOW,
            ),
        }

    def _daily_counts(self, spec, days):
        """Records created per day over the last `days` days, oldest first.

        One grouped query, not one count per day. The buckets are seeded
        first so a day with no records is a real zero in the series
        rather than a gap the caller has to reconstruct — both the
        sparkline and the chart need a value at every position, and a
        missing day would shift every later one along the axis.

        Counted against the history domain — see _history_domain — for
        the same reason the trend line is: a series bucketed by creation
        date must not be filtered by what the records have become since.

        Returns [] when the model is unusable or the query fails, so
        callers can test the list itself instead of repeating the
        guards.
        """
        records = self._records(spec)
        if records is None or "create_date" not in records._fields:
            return []

        domain = self._history_domain(spec)

        # context_today, so "the last N days" means the user's days,
        # matching the day granularity the grouping below uses.
        today = fields.Date.context_today(self)
        start = today - timedelta(days=days - 1)
        buckets = {start + timedelta(days=offset): 0 for offset in range(days)}

        try:
            groups = records._read_group(
                domain + [
                    ("create_date", ">=", fields.Datetime.to_datetime(start)),
                ],
                groupby=["create_date:day"],
                aggregates=["__count"],
            )
        except Exception:
            _logger.warning(
                "Skipping dashboard series %r", spec["key"], exc_info=True)
            return []

        for day, count in groups:
            # A :day group key is a date on some versions and a datetime
            # on others; only the second answers to .date().
            day = day.date() if hasattr(day, "date") else day
            if day in buckets:
                buckets[day] = count

        return [buckets[start + timedelta(days=offset)] for offset in range(days)]

    def _spark(self, series):
        """The last SPARK_DAYS of a daily series, or [].

        The shape under a metric card's figure. Not a breakdown of that
        figure — the figure counts what is open now and this counts what
        arrived, which is why the two can disagree and why the card
        labels neither as the other.

        A week of zeros is not a shape: rendered, it is a bare baseline
        rule with nothing standing on it, which reads as a chart that
        failed to load rather than as "nothing was created this week" —
        something the figure beside it already says. So an empty week is
        dropped and the card falls back to its subtitle.
        """
        week = series[-SPARK_DAYS:]
        return week if any(week) else []

    # ────────────────────────────────────────────────────────────
    # Chart panel
    # ────────────────────────────────────────────────────────────

    def _build_chart(self, tiles, history, limit=CHART_SERIES):
        """Daily created-record series per app, for the trend chart.

        Built from the tiles that survived their guards and the series
        already counted for them, so this method runs no queries of its
        own — everything it needs was read once in get_dashboard_data.

        One series per model that actually saw activity in the window,
        in _TILES order, capped at `limit`. A model with a flat zero
        series is left out rather than offered as a chip that opens an
        empty chart — the tiles above already report that it has nothing
        in it.

        Only one series is plotted at a time — the client's chips switch
        between them — which is why they ship as peers with no colour of
        their own. Quotations and transfers counted on one pair of axes
        would need two scales, and a chart never gets two.

        None when nothing was created anywhere in the window, so the
        client can drop the panel rather than draw empty axes.
        """
        today = fields.Date.context_today(self)
        start = today - timedelta(days=CHART_WINDOW - 1)
        # Formatted here rather than in the browser: the month name is
        # translatable and the server already knows the user's language,
        # so the axis and the tooltip read in it for free.
        labels = [
            format_date(self.env, start + timedelta(days=offset), date_format="MMM d")
            for offset in range(CHART_WINDOW)
        ]

        series = []
        for tile in tiles:
            if len(series) >= limit:
                break

            counts = history.get(tile["key"]) or []
            if not any(counts):
                continue

            series.append({
                "key": tile["key"],
                "label": tile["label"],
                "icon": tile["icon"],
                "total": sum(counts),
                "points": [
                    {"label": labels[offset], "value": value}
                    for offset, value in enumerate(counts)
                ],
            })

        if not series:
            return None

        return {
            "days": CHART_WINDOW,
            "series": series,
        }

    # ────────────────────────────────────────────────────────────
    # Activity feed
    # ────────────────────────────────────────────────────────────

    def _build_activity(self, limit=4):
        """The newest records across every readable tiled model.

        Deliberately not mail.message: `mail` is not a dependency of
        this theme, and a message feed would show conversations rather
        than work. Reading create_date off the same models the tiles
        already count keeps the feed consistent with the figures above
        it and needs no extra access check.

        Ordered and filtered like the other create_date readings — see
        _history_domain. Every row here says "New <thing>: <name>", a
        claim about when the record appeared, so a quotation confirmed
        yesterday still belongs in the feed for the day it was written.
        The tile's needs-attention domain would have dropped it, and a
        feed that quietly deletes its own entries as work progresses is
        the opposite of a record of what happened.
        """
        entries = []
        for spec in self._TILES:
            records = self._records(spec)
            if records is None or "create_date" not in records._fields:
                continue

            try:
                # `limit` per model, then re-sorted across models below:
                # the newest four overall may all come from one app.
                latest = records.search(
                    self._history_domain(spec),
                    order="create_date desc", limit=limit)
                for record in latest:
                    entries.append({
                        "key": "%s-%s" % (spec["key"], record.id),
                        "text": _(
                            "New %(kind)s: %(name)s",
                            kind=spec["singular"], name=record.display_name,
                        ),
                        "icon": ICON_ROOT + spec["icon"],
                        "model": records._name,
                        "res_id": record.id,
                        "_at": record.create_date,
                    })
            except Exception:
                _logger.warning(
                    "Skipping dashboard activity %r", spec["key"], exc_info=True)
                continue

        entries.sort(key=lambda entry: entry["_at"], reverse=True)
        entries = entries[:limit]
        for entry in entries:
            entry["time_ago"] = self._time_ago(entry.pop("_at"))
        return entries

    def _time_ago(self, when):
        """"10m ago" / "2h ago" / "3d ago" for a datetime in the past.

        Formatted here rather than in the browser because the strings
        are translatable and the server already knows the locale; the
        client would need a second source of truth for the same phrases.
        """
        delta = fields.Datetime.now() - when
        minutes = int(delta.total_seconds() // 60)
        if minutes < 1:
            return _("just now")
        if minutes < 60:
            return _("%sm ago", minutes)
        hours = minutes // 60
        if hours < 24:
            return _("%sh ago", hours)
        return _("%sd ago", hours // 24)

    # ────────────────────────────────────────────────────────────
    # Quick actions
    # ────────────────────────────────────────────────────────────

    def _build_quick_actions(self, limit=5):
        """"New …" shortcuts for the models this user may create.

        Gated on create access, not read: a shortcut that opens a form
        the server will refuse to save is worse than no shortcut. The
        action id is the tile's own action — the client opens it
        directly in form view, which is how Odoo creates a record.
        """
        actions = []
        for spec in self._TILES:
            if len(actions) >= limit:
                break

            records = self._records(spec)
            if records is None or not records.has_access("create"):
                continue

            action = self.env.ref(spec["action"], raise_if_not_found=False)
            if not action:
                continue

            actions.append({
                "key": spec["key"],
                # Not .title()-cased: capitalising a translated string
                # word by word is only right in English.
                "label": _("New %s", spec["singular"]),
                "icon": ICON_ROOT + spec["icon"],
                "action_id": action.id,
                # Open straight on the form view: that is the difference
                # between "New Quotation" and "Quotations".
                "form": True,
            })

        # Settings closes the row, as "System" does in the reference
        # design — and only for someone who can actually open it.
        if len(actions) < limit and self.env.user.has_group("base.group_system"):
            settings = self.env.ref(
                "base_setup.action_general_configuration", raise_if_not_found=False)
            if settings:
                actions.append({
                    "key": "settings",
                    "label": _("Settings"),
                    "icon": ICON_ROOT + "setting.png",
                    "action_id": settings.id,
                    # Settings has no "create a record" reading, so it
                    # opens as itself rather than on a form view.
                    "form": False,
                })

        return actions

    # ────────────────────────────────────────────────────────────
    # Preview panel
    # ────────────────────────────────────────────────────────────

    def _build_preview(self, limit=3):
        """A short list of the current user's own open work, or None.

        Empty counts as a miss on purpose: a database whose user has no
        assigned tasks should see their pipeline rather than an empty
        Tasks panel.
        """
        for source in self._PREVIEW_SOURCES:
            records = self._records(source)
            if records is None:
                continue

            try:
                found = records.search(source["domain"](self), limit=limit)
            except Exception:
                _logger.warning(
                    "Skipping dashboard preview %r", source["model"], exc_info=True)
                continue

            if not found:
                continue

            action = self.env.ref(source["action"], raise_if_not_found=False)
            return {
                "title": source["title"],
                "model": records._name,
                "action_id": action.id if action else False,
                "items": [{
                    "id": record.id,
                    "name": record.display_name,
                    "sub": self._preview_sub(record, source["sub_field"]),
                } for record in found],
            }

        return None

    def _preview_sub(self, record, field_name):
        """The muted second line of a preview row — a stage, a customer.

        Empty rather than raising when the field is missing or the
        related record is unreadable: the row's own name is the part
        that matters, and a secondary label is not worth a failed panel.
        """
        if field_name not in record._fields:
            return ""
        try:
            related = record[field_name]
            return related.display_name if related else ""
        except Exception:
            return ""
