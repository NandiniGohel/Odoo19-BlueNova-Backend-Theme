import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * HomeDashboard — the themed landing page inside the web client.
 *
 * A row of KPI tiles, one per installed app the user may read, built
 * server-side by models/theme_dashboard.py. Clicking a tile opens that
 * app's own list/kanban action, so the dashboard is a signpost rather
 * than a second place where records are managed.
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
            tiles: [],
            userName: "",
            companyName: "",
        });

        // One RPC for the whole page, resolved before the first render.
        //
        // A failure here is not fatal: the greeting still renders and the
        // tiles are simply absent, which is the same thing the user sees on
        // a bare database with no business apps installed.
        onWillStart(async () => {
            try {
                const data = await this.orm.call(
                    "bluenova.theme.dashboard",
                    "get_dashboard_data",
                    []
                );
                this.state.tiles = data.tiles || [];
                this.state.userName = data.user_name || "";
                this.state.companyName = data.company_name || "";
            } catch {
                this.state.tiles = [];
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
     * Open the app behind a tile.
     *
     * `action_id` is false when the action's xmlid could not be resolved
     * — the model is installed but its action was renamed or removed. The
     * tile still shows its number; it just does not navigate, and the
     * template renders it disabled.
     */
    onTileClick(tile) {
        if (tile.action_id) {
            this.action.doAction(tile.action_id);
        }
    }
}

registry.category("actions").add("bluenova_dashboard", HomeDashboard);
