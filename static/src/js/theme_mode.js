import { reactive } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";

/**
 * Light/dark preference, shared by whoever needs to read or flip it.
 * Remembered per browser; no server round-trip, so it applies instantly
 * and survives a reload.
 *
 * On 14 this was an `odoo.define` module and interested widgets listened
 * on core.bus. Odoo 19 has OWL 2, so the store is a `reactive()` object
 * instead: a component that does `useState(themeMode)` re-renders on a
 * write with no subscription to wire up and none to tear down.
 *
 * Note this is *not* Odoo 19's own dark mode (the `color_scheme` cookie
 * and the web.assets_web_dark bundle). That switch rebuilds a second
 * asset bundle server-side and reloads the page; this one is a single
 * attribute on <html> that scss/dark_mode.scss keys on, so it flips
 * instantly and is what the theme's own palette — and the Dark Mode
 * Colors pickers under Settings — are written against.
 */

const STORAGE_KEY = "cmt_color_scheme";

/**
 * The whole dark palette hangs off a single attribute on <html>, which
 * scss/dark_mode.scss keys on. Setting it on the document element rather
 * than on .o_web_client means dialogs, popovers and tooltips — which Odoo
 * appends to <body> — are covered too.
 *
 * @param {"light"|"dark"} mode
 */
function applyToDocument(mode) {
    document.documentElement.setAttribute("data-cmt-theme", mode);
}

/** Stored preference, defaulting to light when there is nowhere to read. */
function readStoredMode() {
    try {
        return browser.localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
    } catch {
        // Private browsing with storage disabled: no stored preference.
        return "light";
    }
}

export const themeMode = reactive({
    mode: readStoredMode(),
});

/** @returns {boolean} */
export function isDarkMode() {
    return themeMode.mode === "dark";
}

/**
 * Flip the scheme and remember it.
 *
 * @returns {"light"|"dark"} the new mode
 */
export function toggleThemeMode() {
    themeMode.mode = themeMode.mode === "dark" ? "light" : "dark";
    applyToDocument(themeMode.mode);
    try {
        browser.localStorage.setItem(STORAGE_KEY, themeMode.mode);
    } catch {
        // Nothing to persist to — the flip still applies for this page.
    }
    return themeMode.mode;
}

// Apply the stored choice as soon as the bundle runs, so a dark session
// doesn't flash light while the web client boots.
applyToDocument(themeMode.mode);
