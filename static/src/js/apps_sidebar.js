import { Component, onWillUnmount, reactive, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { themeModeState } from "./theme_mode";

const ICON_ROOT = "/bluegray_modern_theme/static/src/image/icons/";
const STORAGE_KEY = "cmt_apps_sidebar_open";

/** Neutral placeholder, so an app we have no artwork for still gets a row. */
const ICON_FALLBACK = "generic-app.svg";

/**
 * What Odoo puts in `webIconData` when an app has no icon of its own.
 *
 * web/models/ir_ui_menu.py builds that field three ways: a full
 * `data:<mime>;base64,…` URI when the module ships
 * static/description/icon.png, nothing at all when web_icon names a built
 * font icon — and, for everything else, this literal *path*. It is a URL,
 * not image data, so it has to be recognised rather than decoded: read as
 * base64 it produced `data:image/png;base64,/web/static/…`, which is not
 * valid base64, and every custom app in the rail rendered as the browser's
 * broken-image glyph.
 *
 * Treated as "this app has no icon" rather than followed, so those apps get
 * the bundled placeholder — single-colour and mask-painted like the rest of
 * the rail — instead of Odoo's full-colour default sitting among them.
 */
const ODOO_DEFAULT_ICON_PATH = "/web/static/img/default_icon_app.png";

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
 * and Settings. Odoo's own artwork is no help for either: the images
 * behind `base,static/description/*.png` are white line art drawn for the
 * dark app drawer, so on a light sidebar they render as an invisible square.
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
 * Apps with no entry here fall back to their own Odoo icon — see iconFor().
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
    static template = "bluegray_modern_theme.AppsSidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.sidebar = useState(appsSidebarState);
        this.theme = useState(themeModeState);

        // App ids whose icon failed to load, keyed rather than kept in a Set
        // so OWL's reactivity picks the write up. See onIconError().
        this.state = useState({ brokenIcons: {} });

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
        return ICON_ROOT + "employee.png";
    }

    /**
     * Icon for an app: bundled artwork first, then the app's own Odoo icon
     * (base64 from the menu payload), then the neutral placeholder — so an
     * app we have no artwork for still renders a row rather than a gap, and
     * never borrows another app's icon.
     *
     * "The app's own icon" is only the middle branch when Odoo actually has
     * one. Its stand-in path and any icon that failed to load both drop
     * straight through to the placeholder — see ODOO_DEFAULT_ICON_PATH.
     *
     * `bundled` tells the template which of the two it got. The bundled set
     * is single-colour, so the template paints it through a CSS mask and the
     * colour follows hover/active state; Odoo's own icons are full-colour
     * artwork that has to be drawn as-is. The two cannot share a class.
     */
    iconFor(app) {
        const name = (app.name || "").toLowerCase().trim();
        const module = (app.xmlid || "").split(".")[0];
        const file =
            ICON_BY_NAME_FIRST[name] ||
            ICON_BY_XMLID[app.xmlid] ||
            ICON_BY_MODULE[module] ||
            ICON_BY_NAME[name];
        if (file) {
            // Several filenames contain spaces.
            return { src: ICON_ROOT + encodeURIComponent(file), bundled: true };
        }
        const iconData = app.webIconData;
        // An icon that already failed to load once: never offer it again, or
        // the <img> reinstates the broken glyph on every re-render.
        if (iconData && !this.state.brokenIcons[app.id] && iconData !== ODOO_DEFAULT_ICON_PATH) {
            if (iconData.startsWith("data:image")) {
                return { src: iconData, bundled: false };
            }
            // Any other URL Odoo may hand us — served as-is, not decoded.
            if (iconData.startsWith("/") || iconData.startsWith("http")) {
                return { src: iconData, bundled: false };
            }
            // Same sniff Odoo uses in menu_providers.js: base64 SVG starts with "P" ("<").
            const prefix = iconData.startsWith("P")
                ? "data:image/svg+xml;base64,"
                : "data:image/png;base64,";
            return { src: prefix + iconData.replace(/\s/g, ""), bundled: false };
        }
        return { src: ICON_ROOT + ICON_FALLBACK, bundled: true };
    }

    /**
     * An app icon that would not decode — a truncated attachment, a mimetype
     * that lies about its payload. Recorded so the row re-renders onto the
     * bundled placeholder: an <img> that errors is left showing the browser's
     * broken-image glyph, which is worse than no artwork at all.
     */
    onIconError(app) {
        if (!this.state.brokenIcons[app.id]) {
            this.state.brokenIcons[app.id] = true;
        }
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
