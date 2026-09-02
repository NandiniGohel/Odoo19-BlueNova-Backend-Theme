import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatInteger } from "@web/views/fields/formatters";

/**
 * HomeDashboard — the themed landing page inside the web client.
 *
 * The layout follows screen.png / DESIGN.md: two gradient hero cards
 * carrying the largest figures, a recent-activity panel beside them, a
 * row of metric cards with sparklines and status pills, then quick
 * actions and a preview of the user's own open work.
 *
 * Every region is built server-side by models/theme_dashboard.py from
 * whichever apps are installed and readable, so the dashboard is a
 * signpost rather than a second place where records are managed:
 * clicking anything hands over to that app's own action.
 *
 * On 14 this was a legacy `AbstractAction` with `hasControlPanel = false`.
 * Odoo 19 client actions are OWL components registered in the "actions"
 * registry; a component action gets no control panel unless it renders
 * one, so there is nothing to switch off.
 */
export class HomeDashboard extends Component {
    static template = "bluenova_backend_theme.HomeDashboard";
    // Client actions are handed `action`, `actionId`, `className` and
    // friends by the action service; none of them are read here.
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            heroes: [],
            tiles: [],
            chart: null,
            // Which of the chart's series is plotted. An index rather
            // than a key: the chips render straight off the same array,
            // so there is one ordering to keep in step instead of two.
            chartIndex: 0,
            activity: [],
            quickActions: [],
            preview: null,
            userName: "",
            companyName: "",
        });

        // One RPC for the whole page, resolved before the first render.
        //
        // A failure here is not fatal: the greeting still renders and the
        // regions are simply absent, which is the same thing the user sees
        // on a bare database with no business apps installed.
        onWillStart(async () => {
            try {
                const data = await this.orm.call(
                    "bluenova.theme.dashboard",
                    "get_dashboard_data",
                    []
                );
                this.state.heroes = data.heroes || [];
                this.state.tiles = data.tiles || [];
                this.state.chart = data.chart || null;
                this.state.activity = data.activity || [];
                this.state.quickActions = data.quick_actions || [];
                this.state.preview = data.preview || null;
                this.state.userName = data.user_name || "";
                this.state.companyName = data.company_name || "";
            } catch {
                this.state.heroes = [];
                this.state.tiles = [];
                this.state.chart = null;
            }
        });
    }

    /** Time-of-day greeting, in the browser's local time. */
    get greeting() {
        const hour = new Date().getHours();
        if (hour < 12) {
            return _t("Good morning");
        }
        if (hour < 18) {
            return _t("Good afternoon");
        }
        return _t("Good evening");
    }

    /**
     * True when the server found nothing at all to show.
     *
     * Quick actions and the preview panel are deliberately not part of
     * this test: neither can be populated when there is no readable
     * model to build a figure from, so the figures are the whole
     * question.
     */
    get isEmpty() {
        return !this.state.heroes.length && !this.state.tiles.length;
    }

    /**
     * A count, with the thousands separator this user's language uses.
     *
     * formatInteger rather than toLocaleString: the browser's locale and
     * the Odoo user's language are two different settings, and the rest
     * of the backend formats numbers with the second one.
     */
    formatValue(value) {
        return formatInteger(value);
    }

    /**
     * Bar heights for a sparkline, as percentages of its tallest day.
     *
     * A zero day gets zero height, not a stub. The floor here used to
     * be 8% for every bar including the empty ones, which drew a quiet
     * week as seven equal ticks — a dashed line across the card that
     * read as a broken chart rather than as "nothing happened". The
     * spark now sits on a drawn baseline instead (see
     * home_dashboard.scss), so an empty day is visible as a gap in the
     * series rather than as a mark of its own.
     *
     * The 12% floor still applies to days that *did* see something: one
     * record against a peak of thirty is a third of a pixel, and a real
     * value must never round away to nothing.
     */
    sparkBars(spark) {
        const max = Math.max(...spark, 1);
        return spark.map((value) =>
            value > 0 ? Math.max(12, Math.round((value / max) * 100)) : 0
        );
    }

    // ────────────────────────────────────────────────────────
    // Chart panel
    //
    // A day-by-day column chart of records created, one series per app,
    // switched by the chips above it. The geometry is worked out here
    // and handed to the template as percentages, so the bars are laid
    // out by the grid in home_dashboard.scss and reflow with the panel
    // — no viewBox to keep in step with the panel's real width, and no
    // charting library for a single series of counts.
    //
    // One series at a time on purpose: "quotations created" and
    // "transfers created" are counts of different things, and plotting
    // both would need two y-scales. A chart never gets two.
    // ────────────────────────────────────────────────────────

    /** The series currently plotted, or null when there is no chart. */
    get chartSeries() {
        const chart = this.state.chart;
        if (!chart || !chart.series.length) {
            return null;
        }
        // Clamped rather than trusted: chartIndex is state, and a series
        // list that came back shorter than last render would otherwise
        // index off the end.
        const index = Math.min(this.state.chartIndex, chart.series.length - 1);
        return chart.series[index];
    }

    /**
     * The top of the y-axis: the series maximum rounded up to a clean
     * number that also halves cleanly, so the midpoint gridline gets a
     * whole-number label rather than "2.5 records".
     *
     * A peak that is already clean — 6, 10, 100 — is kept as the
     * ceiling rather than pushed to the next step up. Its bar then
     * reaches the top gridline, which is what the top gridline is for;
     * stepping past it would spend half the plot's height on empty
     * space to avoid a bar touching a line it is supposed to touch.
     */
    get chartMax() {
        const series = this.chartSeries;
        const peak = series ? Math.max(...series.points.map((point) => point.value)) : 0;
        if (peak <= 0) {
            return 2;
        }
        const magnitude = Math.pow(10, Math.floor(Math.log10(peak)));
        // 1/2/4/6/10 rather than the usual 1/2/5: five halves to two
        // and a half, and "2.5 records" is not a number of records. The
        // halving is tested rather than assumed because step 1 at
        // magnitude 1 has the same problem — a peak of one would give a
        // ceiling of one and a midpoint tick reading "0.5".
        for (const step of [1, 2, 4, 6, 10]) {
            const candidate = step * magnitude;
            if (candidate >= peak && (candidate / 2) % 1 === 0) {
                return candidate;
            }
        }
        return 10 * magnitude;
    }

    /**
     * One column per day: its label, its value and its height as a
     * percentage of the plot.
     *
     * A zero day gets height 0 and no bar at all — the baseline is
     * already drawn under the plot, and a minimum-height stub on every
     * empty day turns a quiet month into a dashed line that looks like
     * a broken chart. The column stays hoverable either way, so the
     * tooltip can still say "Aug 14 · 0".
     */
    get chartBars() {
        const series = this.chartSeries;
        if (!series) {
            return [];
        }
        const max = this.chartMax;
        return series.points.map((point, index) => ({
            index,
            label: point.label,
            value: point.value,
            height: point.value > 0 ? (point.value / max) * 100 : 0,
        }));
    }

    /**
     * The y-axis: top, midpoint and baseline, as a label plus the
     * distance from the top of the plot the gridline sits at.
     */
    get chartTicks() {
        const max = this.chartMax;
        return [
            { key: "max", label: formatInteger(max), offset: 0 },
            { key: "mid", label: formatInteger(max / 2), offset: 50 },
            { key: "zero", label: "0", offset: 100 },
        ];
    }

    /**
     * The x-axis: the first, middle and last day.
     *
     * Three labels, not thirty. At a column every ~25px a date label is
     * wider than its own column, so a label per day would either
     * overlap or have to be rotated — and the tooltip already carries
     * the exact day for any column the reader points at.
     */
    get chartAxis() {
        const series = this.chartSeries;
        if (!series) {
            return [];
        }
        const points = series.points;
        const middle = Math.floor((points.length - 1) / 2);
        return [points[0], points[middle], points[points.length - 1]]
            .filter(Boolean)
            .map((point) => point.label);
    }

    /** Switch the chart to another app's series. */
    onSelectSeries(index) {
        this.state.chartIndex = index;
    }

    /**
     * Open the app behind a tile or hero card.
     *
     * `action_id` is false when the action's xmlid could not be resolved
     * — the model is installed but its action was renamed or removed. The
     * card still shows its number; it just does not navigate, and the
     * template renders it disabled.
     */
    onTileClick(tile) {
        if (tile.action_id) {
            this.action.doAction(tile.action_id);
        }
    }

    /**
     * Run a quick action.
     *
     * `form: true` means "create one of these": the action opens on its
     * form view with no record loaded, which is Odoo's own new-record
     * path. Settings has no such reading and opens as itself.
     */
    onQuickAction(quickAction) {
        this.action.doAction(
            quickAction.action_id,
            quickAction.form ? { viewType: "form" } : {}
        );
    }

    /**
     * Open one record from the activity feed or the preview list.
     *
     * An ad-hoc act_window rather than the app's action with a res_id:
     * the feed mixes models, and this is the one shape that opens any of
     * them straight on the record the row names.
     */
    openRecord(resModel, resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("bluenova_dashboard", HomeDashboard);
