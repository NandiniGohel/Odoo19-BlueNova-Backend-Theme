import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { session } from "@web/session";
import { useBus, useService } from "@web/core/utils/hooks";

import { themeMode, toggleThemeMode } from "./theme_mode";
import { applySidebarBodyClass, sidebarState } from "./apps_sidebar_state";

/**
 * AppsSidebar — the persistent app rail that replaces Odoo's apps dropdown.
 *
 * Lists every app the user has access to (the same `menuService.getApps()`
 * the dropdown is built from), each with its bundled icon, and marks the
 * one currently open.
 *
 * On 14 this was a legacy `web.Widget` rendered through core.qweb, parented
 * to web.Menu so `app_clicked` could reach the WebClient through
 * trigger_up. Odoo 19 has no widget tree and no core.bus: this is a plain
 * OWL 2 component mounted by the WebClient (see apps_sidebar_patch.js),
 * it reads the menus from the `menu` service, and opening an app is a
 * direct `menuService.selectMenu()` call.
 */

const ICON_ROOT = "/bluenova_backend_theme/static/src/image/icons/";

/** Neutral placeholder, so an app we have no artwork for still gets a row. */
const ICON_FALLBACK = "custom.png";

/**
 * Display names that have to be checked before anything else.
 *
 * `account.menu_finance` is the app root for both Invoicing and Accounting —
 * one module, one xmlid, renamed once account_accountant is installed — so
 * the displayed name is the only thing that tells the two apart. Everything
 * else is matched on the xmlid or module below, which keeps working in
 * every language; this map does not, hence the single entry.
 */
const ICON_BY_NAME_FIRST = {
    accounting: "accounting.png",
};

/**
 * Icon per exact xmlid, checked before the module map below.
 *
 * Only needed where one module owns several app menus and keying on the
 * module alone would hand both of them the same icon — `base` owns Apps
 * and Settings.
 */
const ICON_BY_XMLID = {
    "base.menu_administration": "setting.png",
    "base.menu_management": "apps.svg",
};

/**
 * Bundled icon per Odoo module, keyed on the module part of the app's
 * xmlid (`crm.crm_menu_root` → `crm`). Matching on the module rather than
 * on the displayed name keeps the mapping working in every language.
 *
 * Apps with no entry here fall back to their own Odoo icon — see getIcon().
 */
const ICON_BY_MODULE = {
    account: "invoice.png",
    account_accountant: "accounting.png",
    appointment: "appointment.png",
    barcodes: "barcode.png",
    calendar: "calendar.png",
    contacts: "contacts.png",
    crm: "crm.png",
    data_recycle: "data-recycle.png",
    discuss: "discuss.png",
    event: "events.png",
    fleet: "fleet.png",
    helpdesk: "help desk.png",
    hr: "employee.png",
    hr_appraisal: "appraisal.png",
    hr_attendance: "attendance.png",
    hr_expense: "expense.png",
    hr_holidays: "timeoff.png",
    hr_recruitment: "recruitment.png",
    hr_skills: "skil-management.png",
    hr_timesheet: "timesheet.png",
    im_livechat: "live-chat.png",
    industry_fsm: "field services.png",
    knowledge: "knowladge.png",
    lunch: "lunch.png",
    mail: "discuss.png",
    maintenance: "maintenance.png",
    marketing_automation: "marketing automation.png",
    marketing_card: "marketing-card.png",
    mass_mailing: "email-marketing.png",
    mass_mailing_sms: "sms-marketing.png",
    mrp: "manufacturing.png",
    mrp_plm: "plm.png",
    note: "to-do-list.png",
    planning: "planning.png",
    point_of_sale: "pos.png",
    pos_restaurant: "restaurant.png",
    project: "project.png",
    project_todo: "to-do-list.png",
    purchase: "purchase.png",
    quality: "quality.png",
    quality_control: "quality.png",
    repair: "repair.png",
    sale: "sales.png",
    sale_amazon: "amazon connectio.png",
    sale_management: "sales.png",
    sale_subscription: "subscriptions.png",
    sign: "sign.png",
    sms: "sms-marketing.png",
    social: "social marketing.png",
    spreadsheet_dashboard: "dashboards.svg",
    stock: "inventory.png",
    stock_barcode: "barcode.png",
    survey: "surveys.png",
    timesheet_grid: "timesheet.png",
    // Link Tracker's app root is utm.menu_link_tracker_root, not a module
    // of its own — the obvious `link_tracker` key never matches anything.
    utm: "link-tracker.svg",
    voip: "phone.png",
    web_mobile: "android-apple.png",
    web_studio: "studio.png",
    website: "website.png",
    website_hr_recruitment: "online jobs.png",
    website_sale: "ecommerce.png",
    website_slides: "e-learning.png",
};

/**
 * Second-chance lookup on the displayed name, lowercased. Covers apps whose
 * menu root lives in a different module than the one you'd expect (Invoicing
 * is `account`, but so is Accounting) and apps installed without an xmlid.
 */
const ICON_BY_NAME = {
    appointments: "appointment.png",
    apps: "apps.svg",
    attendances: "attendance.png",
    calendar: "calendar.png",
    contacts: "contacts.png",
    crm: "crm.png",
    dashboards: "dashboards.svg",
    "data cleaning": "data-recycle.png",
    discuss: "discuss.png",
    ecommerce: "ecommerce.png",
    elearning: "e-learning.png",
    "email marketing": "email-marketing.png",
    employees: "employee.png",
    events: "events.png",
    expenses: "expense.png",
    "field service": "field services.png",
    fleet: "fleet.png",
    helpdesk: "help desk.png",
    inventory: "inventory.png",
    invoicing: "invoice.png",
    knowledge: "knowladge.png",
    "link tracker": "link-tracker.svg",
    "live chat": "live-chat.png",
    lunch: "lunch.png",
    maintenance: "maintenance.png",
    manufacturing: "manufacturing.png",
    "marketing automation": "marketing automation.png",
    "marketing card": "marketing-card.png",
    mrp: "mrp.png",
    planning: "planning.png",
    plm: "plm.png",
    "point of sale": "pos.png",
    pos: "pos.png",
    project: "project.png",
    purchase: "purchase.png",
    quality: "quality.png",
    recruitment: "recruitment.png",
    repairs: "repair.png",
    restaurant: "restaurant.png",
    sales: "sales.png",
    settings: "setting.png",
    sign: "sign.png",
    skills: "skil-management.png",
    "sms marketing": "sms-marketing.png",
    "social marketing": "social marketing.png",
    studio: "studio.png",
    subscriptions: "subscriptions.png",
    surveys: "surveys.png",
    timesheets: "timesheet.png",
    "time off": "timeoff.png",
    "to-do": "to-do-list.png",
    website: "website.png",
};

export class AppsSidebar extends Component {
    static template = "bluenova_backend_theme.AppsSidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");

        // Both stores are module-level reactives; useState subscribes this
        // component to them and unsubscribes on unmount.
        this.themeMode = useState(themeMode);
        this.sidebar = useState(sidebarState);

        // App ids whose icon failed to load. An <img> that errors is left
        // showing the browser's broken-image glyph, which is worse than no
        // artwork at all, so those rows are re-rendered onto the
        // placeholder. Reactive, so the swap is a re-render rather than a
        // DOM edit behind OWL's back.
        this.brokenIcons = useState({});

        // The menu service has no reactive store; it announces app switches
        // on the env bus. Following it here keeps the active row in step
        // with navigation, including back/forward and direct URL loads.
        useBus(this.env.bus, "MENUS:APP-CHANGED", () => this.render());

        onMounted(applySidebarBodyClass);
        onWillUnmount(() => document.body.classList.remove("cmt-has-sidebar"));
    }

    //--------------------------------------------------------------------------
    // Getters used by the template
    //--------------------------------------------------------------------------

    get apps() {
        return this.menuService.getApps();
    }

    /** Menu id of the app currently open, or undefined. */
    get currentAppId() {
        const app = this.menuService.getCurrentApp();
        return app && app.id;
    }

    /** Header block: which company and database this session is pointed at. */
    get workspace() {
        return {
            name: (user.activeCompany && user.activeCompany.name) || session.db || _t("Workspace"),
            subtitle: session.db || user.name || "",
        };
    }

    get workspaceIcon() {
        return ICON_ROOT + "employee.png";
    }

    get themeToggleLabel() {
        return this.themeMode.mode === "dark" ? _t("Light mode") : _t("Dark mode");
    }

    get themeToggleTitle() {
        return this.themeMode.mode === "dark"
            ? _t("Switch to light mode")
            : _t("Switch to dark mode");
    }

    /**
     * Icon for an app: bundled artwork first, then the app's own Odoo icon
     * (a data: URL built server-side by ir.ui.menu.load_web_menus), then the
     * neutral placeholder — so an app we have no artwork for still renders a
     * row rather than a gap, and never borrows another app's icon.
     *
     * `bundled` tells the template which of the two it got. The bundled set
     * is single-colour, so the template paints it through a CSS mask and the
     * colour follows hover/active state; Odoo's own icons are full-colour
     * artwork that has to be drawn as-is. The two cannot share a class.
     *
     * @param {Object} app a menu from menuService.getApps()
     * @returns {{src: string, bundled: boolean}}
     */
    getIcon(app) {
        if (this.brokenIcons[app.id]) {
            return { src: ICON_ROOT + ICON_FALLBACK, bundled: true };
        }

        const name = (app.name || "").toLowerCase().trim();
        const module = (app.xmlid || "").split(".")[0];

        // Specific icon for the theme's home dashboard created on module installation
        if (module === "bluenova_backend_theme" || app.xmlid === "bluenova_backend_theme.menu_home_dashboard") {
            return { src: "/bluenova_backend_theme/static/description/icon.png", bundled: false };
        }

        const file =
            ICON_BY_NAME_FIRST[name] ||
            ICON_BY_XMLID[app.xmlid] ||
            ICON_BY_MODULE[module] ||
            ICON_BY_NAME[name];
        if (file) {
            // Several filenames contain spaces.
            return { src: ICON_ROOT + encodeURIComponent(file), bundled: true };
        }

        // No bundled icon found — always show the custom fallback icon
        // so any app without known artwork displays custom.png.
        return { src: ICON_ROOT + ICON_FALLBACK, bundled: true };
    }

    /**
     * Real href, so middle-click and ctrl-click open the app in a new tab.
     * Built exactly the way NavBar.getMenuItemHref builds it — Odoo 19
     * routes the web client on paths (`/odoo/action-42`), not on the hash
     * fragment the 14.0 sidebar produced.
     */
    getHref(app) {
        return `/odoo/${app.actionPath || "action-" + app.actionID}`;
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @param {MouseEvent} ev
     * @param {Object} app
     */
    onAppClick(ev, app) {
        // Let the browser handle the modified clicks the href is there for.
        if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button !== 0) {
            return;
        }
        ev.preventDefault();
        if (!app.actionID) {
            // A root with no actionable descendant at all — nothing to open.
            return;
        }
        this.menuService.selectMenu(app);
    }

    onThemeToggleClick() {
        toggleThemeMode();
    }

    /**
     * An app icon that would not decode — a truncated attachment, a mimetype
     * that lies about its payload. Recorded so getIcon() hands out the
     * bundled placeholder on the next render instead.
     *
     * @param {Object} app
     */
    onIconError(app) {
        this.brokenIcons[app.id] = true;
    }
}
