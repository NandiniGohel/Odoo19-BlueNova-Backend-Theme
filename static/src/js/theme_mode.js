import { reactive } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";

const STORAGE_KEY = "cmt_color_scheme";

/**
 * The whole dark palette hangs off a single attribute on <html>, which
 * scss/dark_mode.scss keys on. Setting it on the document element rather
 * than on .o_web_client means dialogs, popovers and tooltips — which Odoo
 * portals out to <body> — are covered too.
 */
function applyToDocument(mode) {
    document.documentElement.dataset.cmtTheme = mode;
}

/**
 * Light/dark preference, shared by whoever needs to read or flip it.
 * Remembered per browser; no server round-trip, so it applies instantly
 * and survives a reload.
 */
export const themeModeState = reactive({
    mode: browser.localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light",

    get isDark() {
        return this.mode === "dark";
    },

    toggle() {
        this.mode = this.mode === "dark" ? "light" : "dark";
        applyToDocument(this.mode);
        try {
            browser.localStorage.setItem(STORAGE_KEY, this.mode);
        } catch {
            // Private browsing / quota — the switch still works for this session.
        }
    },
});

// Apply the stored choice as soon as the bundle runs, so a dark session
// doesn't flash light while the web client boots.
applyToDocument(themeModeState.mode);
