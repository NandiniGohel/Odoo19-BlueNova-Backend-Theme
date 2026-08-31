"""Colour arithmetic behind the settings-driven brand palette.

Not an Odoo model — a plain module imported by res_config_settings.py.

── Why this exists ──────────────────────────────────────────────

The Primary picker on Settings > Theme Settings used to repaint
exactly one custom property, ``--cmt-primary``. But a brand colour in
this theme is not one value, it is a *family*: variables.scss also
declares --cmt-primary-dark (hover/pressed fills), --cmt-primary-light
(active nav rows, list hover, kanban highlights), --cmt-primary-soft
(focus rings), --cmt-on-primary-container, --cmt-primary-rgb and the
app-icon rail's hover/active tints. Every one of those was a hardcoded
indigo, so picking green moved the buttons and left the sidebar hover,
the focus rings and the active-row wash blue.

Worse, Odoo and Bootstrap never read --cmt-* at all. Their brand is
compiled from ``$o-brand-primary`` (see scss/primary_variables.scss),
which is a build-time literal — the settings screen cannot reach it.
What it *can* reach is the handful of custom properties Bootstrap 5.3
puts on :root and then reads from everywhere: --bs-primary-rgb feeds
``.text-bg-primary`` (the "Enterprise" badge on the settings screen)
and every .bg-/.text-/.border-primary utility, and --bs-link-color-rgb
feeds reboot's ``a`` rule (every blue link in the backend).

So the settings block emits, from the one picked colour: the whole
--cmt-* brand family, and the Bootstrap :root brand vars. Both are
derived here rather than added as more pickers — asking an admin to
choose eight coordinated shades to change one brand colour is the
problem, not the feature.

── Why HSL, not channel mixing ──────────────────────────────────

Darkening by mixing toward black desaturates as it goes, which turns a
vivid green into a muddy olive at the hover state. Working in HSL keeps
the hue fixed and moves lightness and saturation independently, so a
ramp derived from #16a34a reads as the same green throughout — the way
the hand-picked indigo ramp in variables.scss does.

The multipliers below were fitted against that hand-picked ramp: fed
#3959b0 they reproduce variables.scss's values to within a couple of
percent, and fed #7c9aff they reproduce dark_mode.scss's. That is the
check that matters — a default install must look identical before and
after this module existed.
"""

import colorsys
import re

# Accepted input forms. Deliberately narrower than CSS: these are the
# two shapes Odoo's colour picker emits, and the same pair
# res_config_settings.COLOR_RE admits. Anything else (a named colour,
# hsl(), a gradient) has no sane numeric reading here and is refused by
# returning None, which makes the caller skip derivation entirely and
# fall back to the compiled defaults.
_HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
_RGB_RE = re.compile(
    r"^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*[\d.%]+\s*)?\)$"
)

# What sits *on* a brand fill. Not black and white: the light option is
# plain white, but the dark option is the theme's own canvas (#0b1120,
# --cmt-bg in dark mode) rather than #000, so a pale brand reads as a
# hole punched in the surface instead of a black slab.
_ON_LIGHT = "#ffffff"
_ON_DARK = "#0b1120"


def parse(value):
    """Return ``(r, g, b)`` in 0–255 for a CSS colour, or None.

    Alpha is parsed but dropped: every derivation below re-applies its
    own alpha (--cmt-primary-soft) or produces an opaque colour, and a
    half-transparent brand would compound alpha at every step.
    """
    if not value:
        return None
    value = value.strip()

    match = _HEX_RE.match(value)
    if match:
        digits = value[1:]
        if len(digits) in (3, 4):          # #rgb / #rgba
            digits = "".join(c * 2 for c in digits)
        return (
            int(digits[0:2], 16),
            int(digits[2:4], 16),
            int(digits[4:6], 16),
        )

    match = _RGB_RE.match(value)
    if match:
        return tuple(
            max(0, min(255, int(round(float(g))))) for g in match.groups()
        )

    return None


def to_hex(rgb):
    """``(r, g, b)`` → ``#rrggbb``."""
    return "#%02x%02x%02x" % tuple(
        max(0, min(255, int(round(c)))) for c in rgb
    )


def to_triplet(rgb):
    """``(r, g, b)`` → ``"57, 89, 176"``.

    The bare-triplet form Bootstrap wants for the custom properties it
    feeds to ``rgba()`` — --bs-primary-rgb, --bs-link-color-rgb — and
    the form --cmt-primary-rgb already uses for the theme's own focus
    rings.
    """
    return "%d, %d, %d" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def _to_hsl(rgb):
    r, g, b = (c / 255.0 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h, s, l


def _from_hsl(h, s, l):
    s = max(0.0, min(1.0, s))
    l = max(0.0, min(1.0, l))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (r * 255, g * 255, b * 255)


def adjust(rgb, saturation=1.0, lightness=1.0, min_sat=None,
           lightness_to=None, clamp_l=None):
    """Move a colour in HSL space, keeping its hue.

    :param float saturation: multiplier applied to S
    :param float lightness: multiplier applied to L
    :param float min_sat: floor for S, applied before the multiplier —
        used by the app-icon tints, which have to stay vivid even when
        the brand they come from is a muted slate
    :param float lightness_to: if given, L is moved this fraction of the
        way toward 1.0 instead of being multiplied. Lightening by
        multiplication stops working near the top of the range (an L of
        .95 × 1.2 clips), which is exactly where the dark scheme's
        already-pale brand sits.
    :param tuple clamp_l: ``(low, high)`` bounds applied to L last
    """
    h, s, l = _to_hsl(rgb)
    if min_sat is not None:
        s = max(s, min_sat)
    s *= saturation
    if lightness_to is not None:
        l = l + (1.0 - l) * lightness_to
    else:
        l *= lightness
    if clamp_l is not None:
        low, high = clamp_l
        l = max(low, min(high, l))
    return _from_hsl(h, s, l)


def luminance(rgb):
    """WCAG relative luminance, 0.0 (black) – 1.0 (white)."""
    channels = []
    for c in rgb:
        c = c / 255.0
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def on_color(rgb):
    """Pick readable ink for text/icons sitting on ``rgb``.

    0.2, not the usual 0.5. The threshold is not a midpoint, it is the
    crossover: white scores ``1.05 / (L + 0.05)`` against the fill and
    the near-black ink scores ``(L + 0.05) / 0.058``, and those two are
    equal at L = 0.197. Above it the dark ink wins, and by a wide
    margin — dark mode's #7c9aff sits at L = 0.36, where white lands at
    2.6:1 (the failure buttons_misc.scss documents on .btn-primary) and
    the canvas ink at 7.1:1.
    """
    return _ON_DARK if luminance(rgb) > 0.2 else _ON_LIGHT


def derive_brand_vars(primary, dark=False):
    """The full brand family for one scheme, from one picked colour.

    :param str primary: the value stored by the Primary picker
    :param bool dark: derive the dark-scheme ramp (shades go *up* in
        lightness, because the dark theme's brand is a pale periwinkle
        sitting on a near-black canvas — see the Brand block at the top
        of scss/dark_mode.scss)
    :returns: ``{css property: value}``, or ``{}`` when ``primary``
        could not be parsed

    Only the shades are here. The picked colour itself is emitted by
    res_config_settings._render_theme_css from its field map, so
    --cmt-primary is deliberately absent — declaring it twice in one
    rule would work, but it would mean two places to change when the
    picker moves.
    """
    rgb = parse(primary)
    if rgb is None:
        return {}

    triplet = to_triplet(rgb)
    ink = on_color(rgb)

    if dark:
        # Pale brand on a near-black canvas: "dark" means *lifted*, and
        # the container tint is a heavily desaturated near-black rather
        # than a wash of white.
        shade = adjust(rgb, lightness_to=0.30)
        container = adjust(rgb, lightness_to=0.55)
        tint = adjust(rgb, saturation=0.55, lightness=1.0, clamp_l=(0.16, 0.24))
        soft_alpha = 0.45
        link = rgb
        link_hover = adjust(rgb, lightness_to=0.25)
        border_subtle = adjust(rgb, saturation=0.60, clamp_l=(0.26, 0.34))
    else:
        shade = adjust(rgb, saturation=1.15, lightness=0.78)
        container = adjust(rgb, saturation=1.30, lightness=0.62)
        tint = adjust(rgb, min_sat=0.85, clamp_l=(0.955, 0.97))
        soft_alpha = 0.35
        link = adjust(rgb, lightness=0.92)      # Odoo: darken($o-brand-primary, 5%)
        link_hover = adjust(rgb, lightness=0.75)
        border_subtle = adjust(rgb, min_sat=0.60, clamp_l=(0.78, 0.86))

    derived = {
        # ── The theme's own brand family ─────────────────────────
        # Every one of these is read by rules in apps_sidebar.scss,
        # buttons_misc.scss, navbar.scss, control_panel.scss and
        # dark_mode.scss. Leaving them at their compiled defaults is
        # what made a green Primary produce a blue sidebar hover.
        "--cmt-primary-rgb": triplet,
        "--cmt-primary-dark": to_hex(shade),
        "--cmt-primary-light": to_hex(tint),
        "--cmt-primary-soft": "rgba(%s, %s)" % (triplet, soft_alpha),
        "--cmt-on-primary-container": to_hex(container),
        "--cmt-on-primary": ink,
    }

    # ── Bootstrap's :root brand vars ─────────────────────────────
    # The bridge to core. Bootstrap declares these on `:root` and reads
    # them from the utilities and from reboot, so redeclaring them here
    # — under a heavier selector, in a <style> that lands after the
    # bundle — repaints .bg-primary / .border-primary, the
    # "Enterprise" badge and every plain link.
    #
    # Written *unprefixed* and emitted twice, below. Which spelling
    # Bootstrap actually ships is a build-time decision:
    # web/static/src/scss/bootstrap_overridden.scss sets
    # `$variable-prefix: ''`, so on this Odoo the live properties are
    # --primary, --link-color-rgb, --primary-text-emphasis… with no
    # prefix, while stock Bootstrap and older Odoo use --bs-.
    #
    # Emitting only one spelling means the whole block is inert on half
    # the versions this theme claims to support, and inert silently —
    # the CSS is valid, it just names a property nobody reads. Both go
    # out, exactly as the cmt-bs-vars mixin in scss/base.scss does for
    # the stylesheet side.
    bootstrap = {
        "primary": to_hex(rgb),
        "primary-rgb": triplet,
        "link-color": to_hex(link),
        "link-color-rgb": to_triplet(link),
        "link-hover-color": to_hex(link_hover),
        "link-hover-color-rgb": to_triplet(link_hover),
        "primary-bg-subtle": to_hex(tint),
        "primary-border-subtle": to_hex(border_subtle),
        "primary-text-emphasis": to_hex(container),
    }
    for name, value in bootstrap.items():
        derived["--%s" % name] = value
        derived["--bs-%s" % name] = value

    return derived


def derive_icon_vars(primary):
    """The sidebar app-icon rail's hover and active tints.

    Split out from derive_brand_vars() because these two are emitted
    into *both* scheme blocks from the *light* primary, the way the
    semantic colours are (see _THEME_SHARED_COLOR_FIELDS). The rail is
    single-colour artwork painted through a CSS mask and it reads the
    same in light and dark on purpose — variables.scss says so, and
    dark_mode.scss leaves the trio alone.

    --cmt-app-icon (the resting grey) is not here: it is a neutral, not
    a brand colour, and tinting it would make every unvisited app in
    the sidebar shout.

    Both are pushed brighter and more saturated than the brand itself.
    The rail is 20px of flat colour with no text on it, so it can carry
    a vivid tint that would be unreadable as a button fill — which is
    why variables.scss's defaults are #3b82f6/#2563eb next to a #3959b0
    brand rather than the brand itself.
    """
    rgb = parse(primary)
    if rgb is None:
        return {}
    return {
        "--cmt-app-icon-hover": to_hex(
            adjust(rgb, min_sat=0.90, lightness=1.25, clamp_l=(0.45, 0.68))),
        "--cmt-app-icon-active": to_hex(
            adjust(rgb, min_sat=0.88, lightness=1.05, clamp_l=(0.40, 0.58))),
    }
