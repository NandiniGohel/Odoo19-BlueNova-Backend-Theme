/** @odoo-module **/

/**
 * Patch CrmKanbanRenderer to include the stats banner component and
 * use a custom template that injects it above the kanban groups.
 *
 * Why static property assignment instead of patch()?
 *   Odoo's patch() utility patches the *prototype* (instance methods).
 *   `components` and `template` are static class properties, so we set
 *   them directly on the constructor.  This is the standard Odoo
 *   approach for adding sub-components to an existing OWL class.
 */
import { CrmKanbanRenderer } from "@crm/views/crm_kanban/crm_kanban_renderer";
import { CrmPipelineStats } from "@bluenova_backend_theme/js/crm_pipeline_stats";

try {
    CrmKanbanRenderer.components = {
        ...CrmKanbanRenderer.components,
        CrmPipelineStats,
    };

    // Point to the primary-inherited template that prepends the stats
    // banner before the kanban renderer div.
    CrmKanbanRenderer.template = "bluenova_backend_theme.CrmKanbanRenderer";
} catch (e) {
    console.warn(
        "[bluenova_backend_theme] Could not patch CRM kanban renderer for stats banner:",
        e
    );
}
