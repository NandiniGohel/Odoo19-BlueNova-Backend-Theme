/** @odoo-module **/

const { hooks } = owl;
const { onWillUnmount } = hooks;

/**
 * State shared between components that are not in a parent/child relationship
 * — here, the navbar's apps button and the sidebar it opens, which sit in
 * different branches of the WebClient tree.
 *
 * OWL 2's module-level `reactive()` is the natural tool for this and is what
 * this theme used, but Odoo 15 ships owl 1.4.11, which has no such export.
 * `useState` is not a stand-in either: in OWL 1 every component owns its own
 * `Observer` with its own WeakMap of proxies (owl.js, `class Observer`), so
 * two components calling useState() on the same object each get a *different*
 * proxy wrapping it, and a write through one only ever fires that component's
 * notify callback. The sidebar would simply never hear the button's click.
 *
 * Hence an explicit subscription list. The state object stays plain — read it
 * directly, mutate it through its own methods, and call notify() once the
 * mutation is done.
 *
 * @param {Object} state the shared object; gains a `subscribe` method
 * @returns {{ state: Object, notify: () => void }}
 */
export function makeSharedState(state) {
    const listeners = new Set();

    state.subscribe = (callback) => {
        listeners.add(callback);
        return () => listeners.delete(callback);
    };

    return {
        state,
        notify: () => {
            for (const callback of [...listeners]) {
                callback();
            }
        },
    };
}

/**
 * Re-render `component` whenever `state` changes, and drop the subscription
 * when it unmounts. The OWL 1 equivalent of `useState(someReactiveObject)`.
 *
 * The component is passed in rather than taken from `Component.current` so the
 * dependency is visible at the call site.
 *
 * @param {Component} component
 * @param {Object} state a state built by makeSharedState()
 * @returns {Object} the same state, for assigning in setup()
 */
export function useSharedState(component, state) {
    const unsubscribe = state.subscribe(() => component.render());
    onWillUnmount(unsubscribe);
    return state;
}
