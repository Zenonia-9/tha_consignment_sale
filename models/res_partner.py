from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_consignment_shop = fields.Boolean(string="Is Consignment Shop")
    consignment_location_id = fields.Many2one(
        "stock.location",
        string="Consignment Location",
        domain=[("usage", "=", "internal")],
        help="Internal stock location representing this shop's consignment stock.",
    )
    consignment_pricelist_id = fields.Many2one("product.pricelist", string="Consignment Pricelist")
    commission_rate = fields.Float(string="Commission %", default=0.0)

    @api.constrains("is_consignment_shop", "consignment_location_id", "commission_rate")
    def _check_consignment_shop(self):
        for partner in self:
            if partner.commission_rate < 0:
                raise ValidationError(_("Commission cannot be negative."))
            if partner.is_consignment_shop and partner.consignment_location_id and partner.consignment_location_id.usage != "internal":
                raise ValidationError(_("Consignment shop location must be an internal location."))
