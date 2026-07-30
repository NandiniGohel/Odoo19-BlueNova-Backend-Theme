import { useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";
import { WebClient } from "@web/webclient/webclient";
import { AppsSidebar, appsSidebarState } from "./apps_sidebar";

// Make AppsSidebar resolvable from the inherited web.WebClient template
// (see xml/apps_sidebar.xml, which slots it in next to the ActionContainer).
WebClient.components = { ...WebClient.components, AppsSidebar };

// The navbar's apps button no longer opens a dropdown — the inherited
// web.NavBar.AppsMenu template turns it into a show/hide switch for the
// sidebar, which needs the shared state on the component.
patch(NavBar.prototype, {
    setup() {
        super.setup();
        this.appsSidebar = useState(appsSidebarState);
    },
});
