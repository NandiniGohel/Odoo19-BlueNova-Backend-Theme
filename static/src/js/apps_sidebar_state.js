import { reactive } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";

/**
 * Open/closed state of the apps rail, shared between the navbar button
 * that toggles it and the rail itself — two components in different
 * branches of the WebClient tree, so neither can own the state.
 *
 * This replaces static/src/js/shared_state.js from the 14.0 module,
 * which hand-rolled a subscription list because OWL 1 gave every
 * component its own proxy for the same object. OWL 2's `reactive()` does
 * exactly this properly, so the whole file collapses to the four lines
 * below.
 */

const STORAGE_KEY = "cmt_apps_sidebar_open";

/** Remembered per browser; open unless explicitly closed. */
function readStoredOpen() {
    try {
        return browser.localStorage.getItem(STORAGE_KEY) !== "false";
    } catch {
        return true;
    }
}

export const sidebarState = reactive({
    open: readStoredOpen(),
});

/**
 * The rail is fixed-positioned and the action manager is offset to clear
 * it, so both sides of the layout hang off one class on <body>.
 */
export function applySidebarBodyClass() {
    document.body.classList.toggle("cmt-has-sidebar", sidebarState.open);
}

/**
 * @returns {boolean} the new state
 */
export function toggleSidebar() {
    sidebarState.open = !sidebarState.open;
    try {
        browser.localStorage.setItem(STORAGE_KEY, String(sidebarState.open));
    } catch {
        // Nothing to persist to — the toggle still applies for this page.
    }
    applySidebarBodyClass();
    return sidebarState.open;
}
