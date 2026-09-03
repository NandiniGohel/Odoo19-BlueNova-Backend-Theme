import {
    Component,
    markup,
    onWillUnmount,
    useEffect,
    useExternalListener,
    useRef,
    useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * ChatLauncher — the floating chat panel on the themed dashboard.
 *
 * A round button pinned to the bottom-right of the dashboard opening a
 * card with two views:
 *
 *   list    the conversations the user has open in Discuss — the same
 *           rows, in the same order, as Discuss's own sidebar, with the
 *           last message under each name.
 *   thread  one conversation: its recent messages, and a composer that
 *           posts into it.
 *
 * Picking a row goes from the first to the second; the arrow in the
 * header comes back. "Open Discuss" is in the header throughout and
 * hands over to the real thing — on the open conversation when there is
 * one.
 *
 * ── Why this is a real chat and not a preview ────────────────
 *
 * Because posting is what makes OdooBot answer. A message posted with
 * `message_type="comment"` runs mail_bot's `_apply_logic` in the same
 * transaction (see mail_bot/models/discuss_channel.py), so the reply is
 * already written by the time the server hands the thread back — the
 * onboarding conversation every fresh database opens with works here
 * exactly as it does in Discuss, in one round trip.
 *
 * What it still is not: a composer with attachments, mentions,
 * reactions, editing, threads or typing notifications. Those are
 * Discuss, they are one click away, and each of them is a component
 * this file would have to reimplement against `@mail/…` imports it
 * cannot take.
 *
 * ── Why `mail` is still not a dependency ─────────────────────
 *
 * The theme depends on `web` and `base_setup`. Nothing here imports
 * from `@mail/…`: an import of a module that is not in the bundle is a
 * load-time failure of the *whole* backend bundle, not a missing
 * feature, so a database without Discuss would get a blank web client
 * rather than a dashboard with no chat button.
 *
 * Everything mail-shaped is therefore reached by name at runtime rather
 * than by import:
 *
 *   • `isAvailable` asks the actions registry whether Discuss's own
 *     client action is registered — the only question that matters,
 *     answered with no import and no RPC.
 *   • live updates come from `bus_service`, looked up in `env.services`
 *     and simply absent on a database without it.
 *   • the messages themselves come from this theme's own model, which
 *     is guarded the same way; see get_chat_messages in
 *     models/theme_dashboard.py.
 */
export class ChatLauncher extends Component {
    static template = "bluenova_backend_theme.ChatLauncher";
    // Rendered by the dashboard template with no props of its own.
    static props = {};

    /**
     * True when this database has Discuss installed.
     *
     * Read by the dashboard template to decide whether the button
     * exists at all — a launcher that can only ever report "no
     * conversations" is worse than no launcher.
     */
    static get isAvailable() {
        return registry.category("actions").contains("mail.action_discuss");
    }

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.root = useRef("root");
        this.scroller = useRef("scroller");
        this.composer = useRef("composer");

        this.state = useState({
            open: false,
            // "list" or "thread". The panel keeps whichever it was left
            // on across a close and a reopen: closing the bubble in the
            // middle of an exchange and having to find the row again is
            // the kind of small loss that stops people using it.
            view: "list",
            // Distinct from `threads.length === 0`: an empty list after
            // a finished load is the "no conversations yet" state, and
            // before one it is just an unopened panel.
            loading: false,
            threads: [],
            // The row the thread view is showing — the whole row, not
            // just its id: the header renders its name and glyph, and
            // both are already in hand from the list.
            thread: null,
            messages: [],
            // Only true for the first load of a conversation. A refresh
            // behind an open thread leaves the messages on screen: the
            // panel flickering to "Loading…" every time somebody types
            // would be worse than a half-second of staleness.
            loadingMessages: false,
            draft: "",
            sending: false,
            // Set when a post came back refused — the user is not a
            // member any more, or the server would not take it. The
            // draft is deliberately kept so the text is not lost.
            error: "",
        });

        // Closed by a click anywhere outside the launcher, which is how
        // every other transient surface in the backend behaves.
        // Capture phase on purpose: a row inside the panel navigates
        // away and unmounts this component, so a bubbling listener
        // would be asking whether a detached node contains the target.
        useExternalListener(document, "click", this.onDocumentClick, { capture: true });
        useExternalListener(document, "keydown", this.onKeydown);

        // ── Live updates ─────────────────────────────────────
        //
        // Discuss broadcasts every new channel message on the bus, and
        // its server side subscribes each websocket to the channels
        // that user is a member of without being asked (see
        // _build_bus_channel_list in mail/models/discuss/ir_websocket.py).
        // So there is nothing to register here: subscribing to the
        // notification is enough, and the payload's channel id is all
        // this panel reads from it — the rest of that payload is a
        // Store blob whose shape belongs to mail.
        //
        // Reached through env.services rather than useService: the
        // latter throws when the service is absent, and `bus` is not a
        // dependency of this theme any more than `mail` is.
        this.bus = this.env.services.bus_service || null;
        if (this.bus) {
            this.onNewMessage = this.onNewMessage.bind(this);
            this.bus.subscribe("discuss.channel/new_message", this.onNewMessage);
            onWillUnmount(() =>
                this.bus.unsubscribe("discuss.channel/new_message", this.onNewMessage)
            );
        }

        // Pin the conversation to its newest message whenever the tail
        // grows — on open, on send, and on anything that arrives while
        // the panel is watching.
        useEffect(
            () => {
                this.scrollToLatest();
            },
            () => [this.state.view, this.state.messages.length]
        );

        // A conversation opens ready to be typed into. Only on the way
        // in: stealing focus back on every refresh would fight the user
        // for their own cursor.
        useEffect(
            (view) => {
                if (view === "thread") {
                    this.composer.el?.focus();
                }
            },
            () => [this.state.view]
        );
    }

    // ────────────────────────────────────────────────────────
    // The panel
    // ────────────────────────────────────────────────────────

    /** Toggle the panel, loading whichever view it opens on. */
    async onToggle() {
        this.state.open = !this.state.open;
        if (this.state.open) {
            await this.refresh();
        }
    }

    close() {
        this.state.open = false;
    }

    /** Reload whatever the panel is currently showing. */
    async refresh() {
        if (this.state.view === "thread" && this.state.thread) {
            await this.loadMessages();
        } else {
            await this.loadThreads();
        }
    }

    // ────────────────────────────────────────────────────────
    // The conversation list
    // ────────────────────────────────────────────────────────

    /**
     * Fetch the conversation list.
     *
     * Re-read on every open rather than cached from the first one: the
     * dashboard is a page people leave open, and a chat list that is an
     * hour stale is worse than the half-second it costs to refresh it.
     *
     * A failure empties the list rather than raising. The panel then
     * shows its empty state with "Open Discuss" still in the header,
     * which is the one thing that always works.
     */
    async loadThreads({ silent = false } = {}) {
        this.state.loading = !silent;
        try {
            this.state.threads = await this.orm.call(
                "bluenova.theme.dashboard",
                "get_chat_threads",
                []
            );
        } catch {
            if (!silent) {
                this.state.threads = [];
            }
        } finally {
            this.state.loading = false;
        }
    }

    /** Open one conversation inside the panel. */
    async openThread(thread) {
        this.state.thread = thread;
        this.state.view = "thread";
        this.state.messages = [];
        this.state.draft = "";
        this.state.error = "";
        await this.loadMessages();
    }

    /**
     * Back to the list.
     *
     * The list is re-read on the way out rather than restored as it
     * was: the conversation just read has a new last message, a cleared
     * unread badge and a new position in the ordering, and showing it
     * with none of those would be showing it wrong.
     */
    async backToList() {
        this.state.view = "list";
        this.state.thread = null;
        this.state.messages = [];
        this.state.error = "";
        await this.loadThreads({ silent: true });
    }

    // ────────────────────────────────────────────────────────
    // One conversation
    // ────────────────────────────────────────────────────────

    /**
     * Fetch the open conversation's messages.
     *
     * `silent` is for the refreshes nobody asked for — a message
     * arriving over the bus — which must not blank the panel they are
     * refreshing.
     */
    async loadMessages({ silent = false } = {}) {
        const thread = this.state.thread;
        if (!thread) {
            return;
        }
        this.state.loadingMessages = !silent && !this.state.messages.length;
        try {
            const messages = await this.orm.call(
                "bluenova.theme.dashboard",
                "get_chat_messages",
                [thread.id]
            );
            // The thread may have been left while the RPC was in
            // flight; dropping a late answer into the panel would put
            // one conversation's messages under another one's name.
            if (this.state.thread?.id === thread.id) {
                this.state.messages = messages.map((message) => this.prepare(message));
            }
        } catch {
            if (!silent) {
                this.state.messages = [];
            }
        } finally {
            this.state.loadingMessages = false;
        }
    }

    /**
     * A message row, ready to render.
     *
     * The body arrives as HTML — it is one, in the database — and is
     * sanitised server-side on the way out (see get_chat_messages).
     * `markup` is what tells `t-out` to render it as markup rather than
     * printing the tags, and is the same call mail's own message model
     * makes on the same string.
     */
    prepare(message) {
        return { ...message, body: markup(message.body || "") };
    }

    /**
     * Send the composer's contents.
     *
     * The whole thread comes back from the post rather than just the
     * sent message, so OdooBot's reply — written server-side in the
     * same transaction — lands with it. See post_chat_message in
     * models/theme_dashboard.py.
     */
    async onSend() {
        const body = this.state.draft.trim();
        if (!body || this.state.sending || !this.state.thread) {
            return;
        }
        const thread = this.state.thread;
        this.state.sending = true;
        this.state.error = "";
        // Cleared before the round trip, not after: the composer has to
        // feel immediate, and the text is put back below if the post is
        // refused. The element is written to directly because nothing
        // binds its value — see onComposerInput.
        this.state.draft = "";
        this.setComposerValue("");
        try {
            const result = await this.orm.call(
                "bluenova.theme.dashboard",
                "post_chat_message",
                [thread.id, body]
            );
            if (this.state.thread?.id !== thread.id) {
                return;
            }
            this.state.messages = (result.messages || []).map((message) =>
                this.prepare(message)
            );
            if (!result.ok) {
                this.state.error = "Message not sent.";
                this.state.draft = body;
                this.setComposerValue(body);
            }
        } catch {
            this.state.error = "Message not sent.";
            this.state.draft = body;
            this.setComposerValue(body);
        } finally {
            this.state.sending = false;
            this.composer.el?.focus();
        }
    }

    /**
     * Enter sends, Shift+Enter breaks the line.
     *
     * The convention every chat uses, and the reason the composer is a
     * textarea rather than an input: a message with a line in it is a
     * normal thing to write, and `plaintext2html` keeps the break.
     */
    onComposerKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.onSend();
        }
    }

    /**
     * Track the draft, and grow the box to fit it.
     *
     * Written by hand rather than with `t-model` because the composer
     * needs two things from the same input event, and t-model owns it.
     * The state is what the send button reads; the height is what makes
     * a two-line message look like two lines.
     */
    onComposerInput(ev) {
        this.state.draft = ev.target.value;
        this.resizeComposer();
    }

    /**
     * Fit the composer to its contents, up to a ceiling.
     *
     * Reset to auto first: a textarea's scrollHeight cannot shrink
     * below the height already set on it, so measuring without this
     * gives a box that only ever grows.
     */
    resizeComposer() {
        const el = this.composer.el;
        if (el) {
            el.style.height = "auto";
            el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
        }
    }

    /** Put text into the composer, and refit it around what it holds. */
    setComposerValue(value) {
        const el = this.composer.el;
        if (el) {
            el.value = value;
            this.resizeComposer();
        }
    }

    /** Keep the newest message in view. */
    scrollToLatest() {
        const el = this.scroller.el;
        if (el) {
            el.scrollTop = el.scrollHeight;
        }
    }

    // ────────────────────────────────────────────────────────
    // Handing over to Discuss
    // ────────────────────────────────────────────────────────

    /**
     * Open Discuss, on a given conversation when one is named.
     *
     * A raw client action rather than mail's own `thread.open()`: that
     * lives behind an `@mail/…` import this file must not take (see the
     * class comment). The shape below is what mail itself hands the
     * action service — see core/web/thread_model_patch.js — and
     * `active_id` is the "<model>_<id>" string its client action parses.
     */
    openDiscuss(channelId) {
        this.close();
        this.action.doAction({
            type: "ir.actions.client",
            tag: "mail.action_discuss",
            context: channelId ? { active_id: `discuss.channel_${channelId}` } : {},
        });
    }

    // ────────────────────────────────────────────────────────
    // Ambient listeners
    // ────────────────────────────────────────────────────────

    /**
     * A message arrived somewhere in Discuss.
     *
     * Only the channel id is read: if it is the open conversation, its
     * tail is re-read; if it is another one, the list behind it now has
     * a different last message and unread count. Both are refreshed
     * from the server rather than patched from the payload — the
     * payload's shape is mail's business, and a re-read is one cheap
     * query against being subtly wrong.
     *
     * Nothing happens while the panel is closed. It reloads on open
     * anyway, and a chat bubble is not worth an RPC per message the
     * user is not looking at.
     */
    onNewMessage(payload) {
        if (!this.state.open) {
            return;
        }
        const channelId = payload?.id;
        if (this.state.view === "thread" && this.state.thread?.id === channelId) {
            this.loadMessages({ silent: true });
        } else if (this.state.view === "list") {
            this.loadThreads({ silent: true });
        }
    }

    onDocumentClick(ev) {
        if (this.state.open && this.root.el && !this.root.el.contains(ev.target)) {
            this.close();
        }
    }

    /**
     * Escape steps back out of the panel one level at a time — the
     * conversation first, then the panel — rather than dismissing the
     * whole thing from inside a conversation, which would throw away
     * the reader's place to close a card they were still using.
     */
    onKeydown(ev) {
        if (ev.key !== "Escape" || !this.state.open) {
            return;
        }
        if (this.state.view === "thread") {
            this.backToList();
            return;
        }
        this.close();
        // Focus goes back to the button that opened the panel, rather
        // than nowhere, so Escape does not strand a keyboard user at
        // the top of the document.
        this.root.el?.querySelector(".cmt-chat__fab")?.focus();
    }
}
