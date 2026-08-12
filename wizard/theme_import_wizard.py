import base64
import binascii
import json

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.res_config_settings import COLOR_RE, METRIC_BOUNDS


class ThemeImportWizard(models.TransientModel):
    """File picker behind Settings > Theme Settings > Import Settings.

    A button on the settings form cannot receive a file, so the upload
    needs somewhere to land: this wizard takes the JSON written by
    `action_export_theme_settings`, validates it, and writes the colours
    back to ir.config_parameter.
    """

    # Renamed from `bluegray.theme.import.wizard` on the 19.0 port: the
    # module is BlueNova, and the model was the last place still
    # carrying the theme's former name. Nothing persists across the
    # rename — this is a TransientModel with no stored records — but the
    # ACL row in security/ir.model.access.csv and the ir.actions.act_window
    # returned by ResConfigSettings.action_import_theme_settings both key
    # on this string and were changed with it.
    _name = "bluenova.theme.import.wizard"
    _description = "Import BlueNova Theme Settings"

    preset_file = fields.Binary(string="Preset File", required=True)
    preset_filename = fields.Char(string="Filename")

    def action_import(self):
        self.ensure_one()

        try:
            raw = base64.b64decode(self.preset_file)
            payload = json.loads(raw.decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError, ValueError) as err:
            raise UserError(_(
                "That file could not be read as JSON.\n\n%(error)s\n\n"
                "Upload a file produced by Export Settings.", error=err))

        if not isinstance(payload, dict) or not isinstance(payload.get("colors"), dict):
            raise UserError(_(
                "That file is not a theme preset.\n\n"
                "A preset is a JSON object with a \"colors\" entry — use "
                "Export Settings to produce one."))

        Settings = self.env["res.config.settings"]
        # Light and dark together — the export writes both, so an import
        # that only knew the light map would reject every preset this
        # module produces as "settings this theme does not recognise".
        known = Settings._all_color_fields()
        colors = payload["colors"]

        # Everything is checked before anything is written, so a preset
        # with one bad entry does not leave the theme half-imported.
        unknown = sorted(set(colors) - set(known))
        if unknown:
            raise UserError(_(
                "This preset contains settings this theme does not "
                "recognise:\n\n%(names)s\n\nIt was most likely exported "
                "from a different theme or a newer version of this one.",
                names="\n".join(unknown)))

        for fname, value in colors.items():
            value = (value or "").strip()
            if value and not COLOR_RE.match(value):
                raise UserError(_(
                    "%(label)s has an invalid colour in this preset: "
                    "%(value)r\n\nExpected a hex code (#3959b0) or an "
                    "rgb()/rgba() value.",
                    label=Settings._fields[fname].string, value=value))

        # The hero type scale. A preset exported before this key existed
        # simply has no "metrics" entry, which reads as "unset them all"
        # — the same way a missing colour already behaves, and the same
        # thing Reset does.
        metrics = payload.get("metrics") or {}
        if not isinstance(metrics, dict):
            raise UserError(_(
                "The \"metrics\" entry in this preset is not a set of "
                "values. Use Export Settings to produce a valid file."))

        known_metrics = Settings._THEME_METRIC_VARS
        unknown_metrics = sorted(set(metrics) - set(known_metrics))
        if unknown_metrics:
            raise UserError(_(
                "This preset contains settings this theme does not "
                "recognise:\n\n%(names)s\n\nIt was most likely exported "
                "from a different theme or a newer version of this one.",
                names="\n".join(unknown_metrics)))

        for fname, value in metrics.items():
            value = str(value or "").strip()
            if not value:
                continue
            low, high = METRIC_BOUNDS[known_metrics[fname][2]]
            try:
                number = int(value)
            except ValueError:
                raise UserError(_(
                    "%(label)s must be a whole number in this preset, "
                    "not %(value)r.",
                    label=Settings._fields[fname].string, value=value))
            if not low <= number <= high:
                raise UserError(_(
                    "%(label)s is %(value)s in this preset; it must be "
                    "between %(low)s and %(high)s.",
                    label=Settings._fields[fname].string, value=number,
                    low=low, high=high))

        icp = self.env["ir.config_parameter"].sudo()
        for source, fnames in ((colors, known), (metrics, known_metrics)):
            for fname in fnames:
                param = Settings._fields[fname].config_parameter
                # A key absent from the preset, or present but empty, is
                # imported as "unset" — the field default takes over,
                # exactly as after a reset. This keeps import and export
                # symmetric: a preset fully describes a theme rather
                # than patching one.
                value = str(source.get(fname) or "").strip()
                if value:
                    icp.set_param(param, value)
                else:
                    icp.search([("key", "=", param)]).unlink()

        return {"type": "ir.actions.client", "tag": "reload"}
