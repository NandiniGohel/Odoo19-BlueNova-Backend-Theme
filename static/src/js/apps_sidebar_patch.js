import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";
import { WebClient } from "@web/webclient/webclient";

import { AppsSidebar } from "./apps_sidebar";
import { sidebarState, toggleSidebar } from "./apps_sidebar_state";

/**
 * Mount the apps sidebar and turn a navbar button into a switch for it.
 *
 * On 14 this was an `include` on the legacy web.Menu widget, which had to
 * insert the rail's element next to the action manager by hand. Odoo 19's
 * client is OWL 2, so the rail is a real component:
 *
 *   • `WebClient.components` gains AppsSidebar, and the template inherit in
 *     static/src/xml/apps_sidebar.xml drops `<AppsSidebar/>` next to
 *     `<NavBar/>` — inside the same `t-if`, so both stand down in
 *     fullscreen mode.
 *   • `NavBar` gains the toggle handler; the same XML file adds the button
 *     right after Odoo's own apps menu.
 *
 * The rail is still fixed-positioned rather than made a flex/grid sibling:
 * Odoo's scroll model is written as `.o_action_manager > .o_action >
 * .o_content { overflow: auto }`, and restructuring that chain is what
 * stops views scrolling.
 */

WebClient.components = {
    ...WebClient.components,
    AppsSidebar,
};

patch(NavBar.prototype, {
    /** Reactive, so the button's pressed state follows the rail. */
    get cmtSidebarOpen() {
        return sidebarState.open;
    },

    onCmtAppsToggleClick(ev) {
        ev.preventDefault();
        toggleSidebar();
        // sidebarState is a plain reactive read here rather than a
        // useState() subscription — NavBar's setup() is core's, and patching
        // a hook into it is more fragile than one explicit render.
        this.render();
    },
});
