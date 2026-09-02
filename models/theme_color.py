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


# ── The neutral ramp ─────────────────────────────────────────────
#
# What derive_surface_vars() below builds out of the Background
# picker, and the mirror image of the brand ramp above: one decision,
# a dozen coordinated values.
#
# Every entry is ``(css property, Δhue, Δlightness, saturation
# factor, saturation cap)``, and every Δlightness is measured from
# *paper* — the
# lightest surface in the scheme, not from the canvas. That anchor is
# what makes the ramp survive an arbitrary pick: a mid-green canvas at
# L .73 still gets a near-white sheet, a hairline border a shade under
# it and near-black ink, because those three are spaced against each
# other rather than against whatever the admin chose. Offsets from the
# canvas would have collapsed the whole ramp into the canvas the
# moment someone picked something that was not already nearly white.
#
# The numbers are fitted, not invented: fed #f8f9fa the light table
# reproduces the Surfaces and Text blocks of variables.scss, and fed
# #0b1120 the dark table reproduces the same blocks in dark_mode.scss
# — both exactly, every channel of every token. That is the check that
# matters — a theme whose Background is left alone must look exactly
# as it did before this derivation existed, and the skip in
# _surface_derived_vars() guarantees the untouched case outright.
#
# Saturation is a *factor* on the picked colour's own, capped: the
# shipped greys carry a little of their hue (Tailwind's slate ramp,
# not neutral grey), so a factor keeps that relationship at any input,
# while the cap stops a vivid brand-as-canvas from turning the muted
# icon colour and the body ink into more of the same shout. Ink runs
# hotter than the mid-ramp on purpose — #111827 is a saturated
# near-black next to a barely-tinted #9ca3af, and that is what the
# 2.36 factor preserves.
#
# The light table's paper carries a saturation even though the colour
# it has to reproduce, #ffffff, has none. At that lightness the
# saturation is free — hsl(210, 20%, 99.9%) rounds to #ffffff on every
# channel — so the shipped white is reproduced either way, and the
# factor is what decides whether a *tinted* canvas gets a sheet that
# belongs to it or a neutral off-white slab sitting on top of it.
#
# The hue column is small and easy to mistake for noise: the shipped
# ramps are not one hue held constant, they drift about ten degrees
# from the canvas toward the ink (#f8f9fa is 210°, #111827 is 221°).
# Reproducing that drift is what takes the fit from "close" to exact,
# and it carries the same relationship onto whatever hue is picked
# instead — a colorsys hue is a turn, not degrees, hence the /360.
_RAMP_ON_LIGHT = (
    ("--cmt-surface",           0.0, 0.0000, 1.20, 0.35),
    ("--cmt-surface-dim",       0.0, -0.0184, 1.20, 0.35),
    ("--cmt-surface-highest",  10.0, -0.0400, 0.86, 0.30),
    ("--cmt-border",           10.0, -0.0890, 0.78, 0.28),
    ("--cmt-scrollbar-thumb",   6.0, -0.1596, 0.73, 0.26),
    ("--cmt-outline",           7.9, -0.3498, 0.64, 0.24),
    ("--cmt-text-muted",        5.0, -0.6576, 0.83, 0.30),
    ("--cmt-text",             10.9, -0.8890, 2.36, 0.45),
)
_RAMP_ON_DARK = (
    ("--cmt-surface",          -0.9, 0.0000, 0.90, 0.55),
    ("--cmt-surface-dim",      -2.1, -0.0255, 0.93, 0.55),
    ("--cmt-surface-highest",  -5.7, 0.0412, 0.67, 0.45),
    ("--cmt-border",           -4.0, 0.0804, 0.70, 0.45),
    ("--cmt-scrollbar-thumb",  -7.6, 0.1333, 0.51, 0.40),
    ("--cmt-outline",          -7.5, 0.3353, 0.33, 0.30),
    ("--cmt-text-muted",       -7.9, 0.5177, 0.41, 0.32),
    ("--cmt-text",             -8.6, 0.7804, 0.65, 0.40),
)

# How far paper sits from the canvas, as a fraction of the distance to
# white. The two schemes stack in opposite directions: on a light
# canvas paper is at the white end and everything else descends from
# it, while on a dark canvas paper is the first step *up* out of the
# near-black (.0535 of the way up from #0b1120 lands on #131c31) and
# the rest of the ramp keeps climbing past it.
#
# The light scheme has two, and which one applies is decided by how
# much colour is actually in the pick. At .95 a canvas of #f8f9fa
# lands paper on #ffffff, which is the shipped white and the whole
# reason that number is what it is — but the same .95 applied to a
# vivid green lands paper on #fafdfa, two or three steps off white per
# channel. That is a real derivation and an invisible one: every panel
# in the backend stays white and a deliberately-picked canvas looks
# like it did nothing to them.
#
# So the fraction slides toward .70 as the canvas gains saturation.
# The window is set so the two shipped canvases sit below it — the
# light one at S .17 — and a picked colour with any real chroma sits
# above it, which is what keeps "an untouched install is exactly what
# it was" and "a picked canvas visibly reaches the panels" from being
# the same dial pulling in opposite directions. Between the two ends
# it interpolates, so there is no step where one more click of
# saturation repaints the whole backend.
_PAPER_ON_LIGHT = 0.95
_PAPER_ON_LIGHT_TINTED = 0.70
_PAPER_ON_DARK = 0.0535

# The saturation window the fraction above slides across: at or below
# _TINT_FROM_SAT the canvas is a neutral and paper stays at white, at
# or above _TINT_FULL_SAT it is a colour and paper comes down to meet
# it.
_TINT_FROM_SAT = 0.20
_TINT_FULL_SAT = 0.45

# The kanban card fill, which is not on the ramp above because the two
# schemes do not build it the same way. On a light canvas it is
# translucent paper over whatever is behind it — the card reads as
# glass because you can see the canvas through it — while dark mode
# makes it opaque on purpose: a translucent fill there composites over
# surfaces core still paints white and comes out a washed grey-blue,
# which is the whole reason dark_mode.scss's Surfaces block says
# "All opaque". So light gets the paper triplet at the two shipped
# alphas, and dark gets two more fitted steps.
_GLASS_ALPHA_ON_LIGHT = (
    ("--cmt-glass-bg", 0.7),
    ("--cmt-glass-bg-hover", 0.95),
)
_GLASS_ON_DARK = (
    ("--cmt-glass-bg",       0.4, 0.0235, 0.92, 0.55),
    ("--cmt-glass-bg-hover", 0.0, 0.0627, 0.86, 0.55),
)

# ...and how far it is allowed to end up from the ink that has to be
# read on it.
#
# Both fractions above are measured from the canvas, which is fine at
# the ends of the range and not fine in the middle: a mid-tone pick
# like #16a34a sits at L .36, so the dark ramp put paper at .39 and
# then had nowhere left to go — its ink clamps at white, and white on
# a .39 green is 3.4:1, under the 4.5:1 floor for body text. The
# theme's own two canvases are nowhere near that band, which is why
# the fitted fractions alone looked sufficient.
#
# Clamping paper rather than boosting the ink is what fixes it: ink is
# already at the end of its travel, and every other step in the ramp
# is spaced from paper, so moving that one number pulls the whole
# scheme back into contrast at once. .30 is where white reaches 4.8:1.
#
# The light floor is its mirror, and it does bind now that paper comes
# down to meet a saturated canvas: it is what stops a vivid mid-tone
# pick from pulling the sheet down with it until the form stops
# reading as paper at all. A canvas at L .55 wants paper at .865 and
# gets .90.
_PAPER_FLOOR_ON_LIGHT = 0.90
_PAPER_CEILING_ON_DARK = 0.30

# Which way the ramp stacks. HSL lightness, not WCAG luminance: this
# picks a *direction* for a ramp, not readable ink for a fill (that is
# on_color()'s job, and its threshold is set by a contrast crossover
# that has no bearing here). A canvas is "light" when there is more
# room below it than above.
_CANVAS_IS_LIGHT_ABOVE = 0.5


def derive_surface_vars(background):
    """The whole neutral ramp for one scheme, from the picked canvas.

    The Background picker used to move exactly one token, --cmt-bg,
    while every neutral around it stayed the compiled Tailwind grey:
    --cmt-surface white, --cmt-border #e5e7eb, --cmt-text near-black —
    and --cmt-bg-rgb, which variables.scss keeps in step with --cmt-bg
    *by hand* because CSS cannot decompose a hex, stayed 248, 249, 250
    however far the canvas moved. So a green canvas came out with white
    sheets, grey hairlines and an empty-view scrim still washing the
    view in the old off-white.

    Which direction the ramp stacks is decided by the picked colour
    itself, not by which block is being emitted: a dark colour chosen
    as the *light* scheme's Background gets the dark ramp, so the ink
    flips to light and the surfaces lift out of the canvas instead of
    sinking into it. That is the case a scheme-driven flag would get
    wrong, and it is not a rare one — "light mode" is where an admin
    who wants one dark theme starts.

    :param str background: the value stored by the Background picker
    :returns: ``{css property: value}``, or ``{}`` when ``background``
        could not be parsed
    """
    rgb = parse(background)
    if rgb is None:
        return {}

    h, s, l = _to_hsl(rgb)
    on_light = l >= _CANVAS_IS_LIGHT_ABOVE
    ramp = _RAMP_ON_LIGHT if on_light else _RAMP_ON_DARK
    if on_light:
        tint = (s - _TINT_FROM_SAT) / (_TINT_FULL_SAT - _TINT_FROM_SAT)
        tint = max(0.0, min(1.0, tint))
        fraction = _PAPER_ON_LIGHT + (
            _PAPER_ON_LIGHT_TINTED - _PAPER_ON_LIGHT) * tint
        paper = max(l + (1.0 - l) * fraction, _PAPER_FLOOR_ON_LIGHT)
    else:
        paper = min(l + (1.0 - l) * _PAPER_ON_DARK, _PAPER_CEILING_ON_DARK)

    tokens = {
        name: to_hex(_from_hsl(
            h + dh / 360.0, min(s * factor, cap), paper + dl))
        for name, dh, dl, factor, cap in ramp
    }

    derived = dict(tokens)
    # The one variables.scss calls out as hand-maintained. This is the
    # line that stops it being hand-maintained.
    derived["--cmt-bg-rgb"] = to_triplet(rgb)

    if on_light:
        paper_rgb = to_triplet(parse(tokens["--cmt-surface"]))
        for name, alpha in _GLASS_ALPHA_ON_LIGHT:
            derived[name] = "rgba(%s, %s)" % (paper_rgb, alpha)
    else:
        for name, dh, dl, factor, cap in _GLASS_ON_DARK:
            derived[name] = to_hex(_from_hsl(
                h + dh / 360.0, min(s * factor, cap), paper + dl))
    # A hairline drawn *on* the glass, so it lifts on a dark card and
    # sits as a shadow on a light one — the same reading as
    # --border-color-translucent below.
    derived["--cmt-glass-border"] = "1px solid rgba(%s, 0.08)" % (
        "0, 0, 0" if on_light else "255, 255, 255")

    ink = tokens["--cmt-text"]
    muted = tokens["--cmt-text-muted"]

    # ── Bootstrap's :root neutrals ───────────────────────────────
    # The same bridge derive_brand_vars() builds for the brand, for
    # the same reason: Bootstrap's neutrals are compiled from
    # $body-bg / $body-color literals that no setting can reach, but
    # the custom properties it puts on :root and reads back from
    # reboot and the utilities can be redeclared from here. Without
    # them a tinted canvas keeps core's white body background showing
    # through everything this theme does not paint by hand.
    #
    # Both spellings again — see the note in derive_brand_vars() and
    # the cmt-bs-vars mixin in scss/base.scss for why the unprefixed
    # one is the one that lands on this Odoo.
    bootstrap = {
        "body-bg": to_hex(rgb),
        "body-bg-rgb": to_triplet(rgb),
        "body-color": ink,
        "body-color-rgb": to_triplet(parse(ink)),
        "emphasis-color": ink,
        "emphasis-color-rgb": to_triplet(parse(ink)),
        # Reboot compiles `h1…h6 { color: var(--heading-color) }` and
        # Odoo seeds it from $o-black. Left alone, every heading in the
        # backend stays pure black whatever the canvas becomes — the
        # same failure dark_mode.scss documents at its heading rule.
        "heading-color": ink,
        "secondary-color": muted,
        "secondary-bg": tokens["--cmt-surface-dim"],
        "tertiary-color": tokens["--cmt-outline"],
        "tertiary-bg": tokens["--cmt-surface-highest"],
        "border-color": tokens["--cmt-border"],
        # Follows the ramp direction, not the scheme: the translucent
        # hairline is a lift on a dark canvas and a shadow on a light
        # one, and the wrong one of the two is invisible.
        "border-color-translucent": (
            "rgba(0, 0, 0, 0.1)" if on_light else "rgba(255, 255, 255, 0.1)"
        ),
    }
    for name, value in bootstrap.items():
        derived["--%s" % name] = value
        derived["--bs-%s" % name] = value

    # Odoo's own, never prefixed (see o-print-color in
    # web/static/src/scss/functions.scss). It is what the `bg-view`
    # utility and a handful of view surfaces read.
    derived["--o-view-background-color"] = tokens["--cmt-surface"]

    return derived
