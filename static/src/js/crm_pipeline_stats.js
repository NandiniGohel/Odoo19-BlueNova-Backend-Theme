/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * CrmPipelineStats — renders a row of summary stat cards above the CRM
 * pipeline kanban.  All numbers are computed from the grouped model data
 * already loaded in memory (no extra RPC).
 *
 * Fails silently (console.warn) if the expected data structure is missing,
 * so it will never break the page even if Odoo's internals change.
 */
export class CrmPipelineStats extends Component {
    static template = "bluenova_backend_theme.PipelineStats";
    static props = {
        list: { type: Object },
    };

    /**
     * Whether the stats banner should render at all.
     * Only shows for grouped kanban with at least one stage.
     */
    get isVisible() {
        try {
            const list = this.props.list;
            return (
                list &&
                list.isGrouped &&
                Array.isArray(list.groups) &&
                list.groups.length > 0
            );
        } catch {
            return false;
        }
    }

    /**
     * Compute the four stat-card values from the grouped model root.
     *
     * Data sources (in preference order):
     *   - group.count           → accurate total per stage (from web_read_group)
     *   - group.aggregates      → server-side field sums (expected_revenue)
     *   - group.list.records    → fallback: sum loaded page of records
     */
    get stats() {
        try {
            const groups = this.props.list.groups;
            if (!groups || !groups.length) {
                return null;
            }

            const totalRecords = groups.reduce(
                (sum, g) => sum + (g.count || 0),
                0
            );

            const share = (count) =>
                totalRecords > 0 ? Math.round((count / totalRecords) * 100) : 0;

            // ── Card 1: first stage ("New" or whatever the pipeline starts with)
            const firstGroup = groups[0];
            const firstCount = firstGroup ? firstGroup.count || 0 : 0;
            const newLeads = {
                count: firstCount,
                label: firstGroup ? firstGroup.displayName || "New" : "New",
                sub: `${share(firstCount)}% of pipeline`,
            };

            // ── Card 2: second stage ("Qualified" or equivalent)
            const secondGroup = groups.length > 1 ? groups[1] : null;
            const secondCount = secondGroup ? secondGroup.count || 0 : 0;
            const qualified = {
                count: secondCount,
                label: secondGroup
                    ? secondGroup.displayName || "Qualified"
                    : "Qualified",
                sub: secondGroup
                    ? `${this._formatCurrency(this._groupRevenue(secondGroup))} in stage`
                    : "No stage",
            };

            // ── Card 3: total expected revenue across all stages
            const totalRevenue = groups.reduce(
                (sum, g) => sum + this._groupRevenue(g),
                0
            );

            // ── Card 4: won deals + conversion rate
            const wonGroup = groups.find((g) =>
                (g.displayName || "").toLowerCase().trim().includes("won")
            );
            const wonDeals = wonGroup ? wonGroup.count || 0 : 0;

            return {
                newLeads,
                qualified,
                revenue: {
                    value: totalRevenue,
                    formatted: this._formatCurrency(totalRevenue),
                    sub: "Total Expected",
                },
                wonDeals: {
                    count: wonDeals,
                    sub: `Conversion: ${share(wonDeals)}%`,
                },
            };
        } catch (e) {
            console.warn(
                "[bluenova_backend_theme] Could not compute pipeline stats:",
                e
            );
            return null;
        }
    }

    /**
     * Expected revenue for a single stage group.
     *
     * `aggregates` is the accurate source — it covers every record in the
     * stage, not just the loaded page. It is absent when the pipeline spans
     * multiple currencies (Odoo refuses to sum those), in which case we fall
     * back to summing whatever records are in memory.
     */
    _groupRevenue(group) {
        const aggregate = group.aggregates && group.aggregates.expected_revenue;
        if (typeof aggregate === "number") {
            return aggregate;
        }

        const records = (group.list && group.list.records) || [];
        return records.reduce((sum, record) => {
            const value = record.data && record.data.expected_revenue;
            return sum + (typeof value === "number" ? value : 0);
        }, 0);
    }

    /**
     * Format a numeric value into a compact currency string.
     * Uses "$" as the default symbol; large values are shortened
     * (e.g. 1 200 000 → "$1.2M").
     */
    _formatCurrency(value) {
        if (value >= 1_000_000) {
            return "$" + (value / 1_000_000).toFixed(1) + "M";
        }
        if (value >= 1_000) {
            return "$" + (value / 1_000).toFixed(1) + "K";
        }
        if (value > 0) {
            return "$" + Math.round(value).toLocaleString();
        }
        return "$0";
    }
}
