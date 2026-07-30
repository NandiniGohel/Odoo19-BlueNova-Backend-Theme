import { Component, onWillUnmount, reactive, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { themeModeState } from "./theme_mode";

const ICON_ROOT = "/crm_modern_theme/static/src/image/icons/";
const STORAGE_KEY = "cmt_apps_sidebar_open";

/**
 * Icon per exact xmlid, checked before the module map below.
 *
 * Needed where one module owns several app menus (`base` has both Apps and
 * Settings), and where Odoo's own icon is unusable: the artwork behind
 * `base,static/description/*.png` is white line art drawn for the dark app
 * drawer, so on a light sidebar it renders as an invisible square.
 */
const ICON_BY_XMLID = {
    "base.menu_administration": "studio.png",
    "base.menu_management": "3d-cube.png",
};

/**
 * Bundled icon per Odoo module, keyed on the module part of the app's
 * xmlid (`crm.crm_menu_root` → `crm`). Matching on the module rather than
 * on the displayed name keeps the mapping working in every language.
 *
 * Apps with no entry here fall back to their own Odoo icon — see iconFor().
 */
const ICON_BY_MODULE = {
    account: "accounting.png",
    account_accountant: "accounting.png",
    appointment: "online-conference.png",
    barcodes: "barcode.png",
    calendar: "calendar.png",
    contacts: "contact.png",
    crm: "crm.png",
    discuss: "dicuss.png",
    event: "events.png",
    fleet: "fleet-management.png",
    helpdesk: "help-desk.png",
    hr: "employees.png",
    hr_appraisal: "appraisal.png",
    hr_attendance: "attdences.png",
    hr_expense: "expenses.png",
    hr_holidays: "time-out.png",
    hr_recruitment: "recruitment.png",
    hr_skills: "skill mahagement.png",
    hr_timesheet: "timesheet.png",
    im_livechat: "live chat.png",
    industry_fsm: "field-services.png",
    knowledge: "knowledge.png",
    lunch: "lunch.png",
    mail: "dicuss.png",
    maintenance: "maintenance.png",
    marketing_automation: "marketing-automation.png",
    marketing_card: "marketing-card.png",
    mass_mailing: "email_marketing.png",
    mass_mailing_sms: "sms marketing.png",
    mrp: "manufacturing.png",
    mrp_plm: "product-chain.png",
    note: "to-do.png",
    planning: "planning.png",
    point_of_sale: "pos.png",
    pos_restaurant: "restaurant.png",
    project: "project.png",
    project_todo: "to-do.png",
    purchase: "purchase.png",
    quality: "quality.png",
    quality_control: "quality.png",
    repair: "reparis.png",
    sale: "sales.png",
    sale_amazon: "amazon connectio.png",
    sale_management: "sales.png",
    sale_subscription: "subscription.png",
    sign: "signature.png",
    sms: "sms marketing.png",
    social: "social marketing.png",
    spreadsheet_dashboard: "3d-cube.png",
    stock: "inventory.png",
    stock_barcode: "barcode.png",
    timesheet_grid: "timesheet.png",
    voip: "phone.png",
    web_studio: "studio.png",
    website: "website.png",
    website_sale: "ecommerce.png",
    website_slides: "elearning.png",
};

/**
 * Second-chance lookup on the displayed name, lowercased. Covers apps whose
 * menu root lives in a different module than the one you'd expect (Invoicing
 * is `account`, but so is Accounting) and apps installed without an xmlid.
 */
const ICON_BY_NAME = {
    accounting: "accounting.png",
    calendar: "calendar.png",
    contacts: "contact.png",
    crm: "crm.png",
    dashboards: "3d-cube.png",
    discuss: "dicuss.png",
    ecommerce: "ecommerce.png",
    elearning: "elearning.png",
    employees: "employees.png",
    "email marketing": "email_marketing.png",
    events: "events.png",
    expenses: "expenses.png",
    "field service": "field-services.png",
    fleet: "fleet-management.png",
    helpdesk: "help-desk.png",
    inventory: "inventory.png",
    invoicing: "invoice.png",
    knowledge: "knowledge.png",
    "live chat": "live chat.png",
    lunch: "lunch.png",
    maintenance: "maintenance.png",
    manufacturing: "manufacturing.png",
    "marketing automation": "marketing-automation.png",
    mrp: "mrp.png",
    planning: "planning.png",
    "point of sale": "pos.png",
    pos: "pos.png",
    project: "project.png",
    purchase: "purchase.png",
    quality: "quality.png",
    recruitment: "recruitment.png",
    repairs: "reparis.png",
    sales: "sales.png",
    sign: "signature.png",
    "sms marketing": "sms marketing.png",
    "social marketing": "social marketing.png",
    studio: "studio.png",
    subscriptions: "subscription.png",
    timesheets: "timesheet.png",
    "time off": "time-out.png",
    "to-do": "to-do.png",
    website: "website.png",
};

/**
 * Open/closed state of the sidebar, shared between the sidebar itself and
 * the navbar button that toggles it. Kept as a module-level `reactive` so
 * both components can subscribe to it without a service round-trip; the
 * choice is remembered per browser.
 */
export const appsSidebarState = reactive({
    isOpen: browser.localStorage.getItem(STORAGE_KEY) !== "false",
    toggle() {
        this.isOpen = !this.isOpen;
        try {
            browser.localStorage.setItem(STORAGE_KEY, String(this.isOpen));
        } catch {
            // Private browsing / quota — the toggle still works for this session.
        }
    },
});

/**
 * AppsSidebar — the persistent app rail that replaces Odoo's apps dropdown.
 *
 * Lists every app the user has access to (same source as the dropdown,
 * menuService.getApps()), each with its bundled icon, and marks the one
 * currently open. Rendered by the WebClient next to the action manager.
 */
export class AppsSidebar extends Component {
    static template = "crm_modern_theme.AppsSidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.sidebar = useState(appsSidebarState);
        this.theme = useState(themeModeState);

        // The menu service has no reactive store; it announces app switches
        // on the bus instead. Re-render on it so the active row follows
        // navigation, including back/forward and direct URL loads.
        const render = () => this.render();
        this.env.bus.addEventListener("MENUS:APP-CHANGED", render);
        onWillUnmount(() => this.env.bus.removeEventListener("MENUS:APP-CHANGED", render));
    }

    get apps() {
        return this.menuService.getApps();
    }

    get currentAppId() {
        const currentApp = this.menuService.getCurrentApp();
        return currentApp && currentApp.id;
    }

    /** Header block: which company and database this session is pointed at. */
    get workspace() {
        return {
            name: user.activeCompany?.name || session.db || "Workspace",
            subtitle: session.db || user.login || "",
        };
    }

    get workspaceIcon() {
        return ICON_ROOT + "employees.png";
    }

    /**
     * Icon for an app: bundled icon first, then the app's own Odoo icon
     * (base64 from the menu payload), then the generic placeholder — so an
     * app we have no artwork for still renders a row rather than a gap.
     *
     * `bundled` tells the template which of the two it got. The bundled set
     * is dark line art on transparent and has to be inverted in dark mode;
     * Odoo's own icons must not be, so the two cannot share a class.
     */
    iconFor(app) {
        const module = (app.xmlid || "").split(".")[0];
        const file =
            ICON_BY_XMLID[app.xmlid] ||
            ICON_BY_MODULE[module] ||
            ICON_BY_NAME[(app.name || "").toLowerCase().trim()];
        if (file) {
            // Several filenames contain spaces and "&".
            return { src: ICON_ROOT + encodeURIComponent(file), bundled: true };
        }
        if (app.webIconData) {
            if (app.webIconData.startsWith("data:image")) {
                return { src: app.webIconData, bundled: false };
            }
            // Same sniff Odoo uses in menu_providers.js: base64 SVG starts with "P" ("<").
            const prefix = app.webIconData.startsWith("P")
                ? "data:image/svg+xml;base64,"
                : "data:image/png;base64,";
            return { src: prefix + app.webIconData.replace(/\s/g, ""), bundled: false };
        }
        return { src: ICON_ROOT + "3d-cube.png", bundled: true };
    }

    /** Real href, so middle-click and ctrl-click open the app in a new tab. */
    hrefFor(app) {
        return `/odoo/${app.actionPath || "action-" + app.actionID}`;
    }

    onAppClick(ev, app) {
        // Let the browser handle the modified clicks the href is there for.
        if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button !== 0) {
            return;
        }
        ev.preventDefault();
        this.menuService.selectMenu(app);
    }
}
