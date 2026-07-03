from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError


class ThaConsignmentSettlementCreateWizard(models.TransientModel):
    _name = "tha.consignment.settlement.create.wizard"
    _description = "Create Consignment Settlement"

    order_id = fields.Many2one("tha.consignment.order", string="Consignment Order", required=True, readonly=True)
    partner_id = fields.Many2one("res.partner", related="order_id.partner_id", string="Customer")
    settlement_date = fields.Date(default=fields.Date.context_today, required=True)
    commission_rate = fields.Float(string="Commission %", default=0.0)
    line_ids = fields.One2many("tha.consignment.settlement.create.wizard.line", "wizard_id", string="Lines")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") != "tha.consignment.order":
            raise UserError(_("This wizard must be opened from a consignment order."))
        order = self.env["tha.consignment.order"].browse(self.env.context.get("active_id")).exists()
        if not order:
            raise UserError(_("The selected consignment order no longer exists."))
        if not order.can_settle:
            raise UserError(_("There is no remaining quantity to settle."))
        line_commands = []
        for line in order.line_ids.filtered(lambda current_line: not current_line.display_type):
            if line.remaining_qty <= 0:
                continue
            line_commands.append(Command.create({
                "sequence": line.sequence,
                "order_line_id": line.id,
                "product_id": line.product_id.id,
                "name": line.name,
                "product_uom_id": line.product_uom_id.id,
                "remaining_qty": line.remaining_qty,
                "quantity": line.remaining_qty,
                "price_unit": line.consignment_price_unit,
                "discount": line.consignment_discount,
            }))
        res.update({
            "order_id": order.id,
            "settlement_date": order.commitment_date or fields.Date.context_today(self),
            "commission_rate": order.commission_rate,
            "line_ids": line_commands,
        })
        return res

    def action_create_draft(self):
        self.ensure_one()
        source_lines = self.order_id.line_ids.filtered(
            lambda order_line: not order_line.display_type and order_line.remaining_qty > 0
        ).sorted(lambda order_line: (order_line.sequence, order_line.id))
        wizard_lines = self.line_ids.sorted(lambda wizard_line: (wizard_line.sequence, wizard_line.id))
        lines_to_create = []
        for index, line in enumerate(wizard_lines.filtered(lambda wizard_line: wizard_line.quantity > 0)):
            order_line = line.order_line_id
            if not order_line and index < len(source_lines):
                order_line = source_lines[index]
            if not order_line:
                continue
            remaining_qty = line.remaining_qty or order_line.remaining_qty
            if line.quantity < 0:
                raise UserError(_("Settlement quantity cannot be negative."))
            if line.quantity > remaining_qty:
                raise UserError(_("Settlement quantity cannot exceed remaining quantity for %s.") % order_line.product_id.display_name)
            lines_to_create.append(Command.create({
                "sequence": line.sequence,
                "order_line_id": order_line.id,
                "product_id": line.product_id.id or order_line.product_id.id,
                "name": line.name or order_line.name,
                "product_uom_qty": line.quantity,
                "product_uom_id": line.product_uom_id.id or order_line.product_uom_id.id,
                "price_unit": line.price_unit or order_line.consignment_price_unit,
                "discount": line.discount or order_line.consignment_discount,
            }))
        if not lines_to_create:
            raise UserError(_("Set at least one quantity greater than zero."))

        order = self.order_id
        invoice_partner = order._prepare_invoice_partner(order.partner_id)
        fiscal_position = (
            self.env["account.fiscal.position"]._get_fiscal_position(order.partner_id, invoice_partner)
            if hasattr(self.env["account.fiscal.position"], "_get_fiscal_position")
            else self.env["account.fiscal.position"]
        )
        settlement = self.env["tha.consignment.settlement"].create({
            "order_id": order.id,
            "partner_id": order.partner_id.id,
            "partner_invoice_id": invoice_partner.id,
            "company_id": order.company_id.id,
            "settlement_date": self.settlement_date,
            "pricelist_id": order.pricelist_id.id,
            "currency_id": order.currency_id.id,
            "commission_rate": self.commission_rate,
            "user_id": order.user_id.id,
            "team_id": order.team_id.id,
            "payment_term_id": order.partner_id.property_payment_term_id.id,
            "fiscal_position_id": fiscal_position.id,
            "warehouse_id": order.destination_warehouse_id.id,
            "source_location_id": order.destination_location_id.id,
            "line_ids": lines_to_create,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Consignment Settlement"),
            "res_model": "tha.consignment.settlement",
            "view_mode": "form",
            "res_id": settlement.id,
            "context": {"create": False},
        }


class ThaConsignmentSettlementCreateWizardLine(models.TransientModel):
    _name = "tha.consignment.settlement.create.wizard.line"
    _description = "Create Consignment Settlement Line"
    _order = "wizard_id, sequence, id"

    wizard_id = fields.Many2one("tha.consignment.settlement.create.wizard", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    order_line_id = fields.Many2one("tha.consignment.order.line", string="Order Line", readonly=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    name = fields.Text(string="Description", readonly=True)
    product_uom_id = fields.Many2one("uom.uom", string="Unit", readonly=True)
    remaining_qty = fields.Float(string="Remaining Qty", digits="Product Unit", readonly=True)
    quantity = fields.Float(string="Quantity", digits="Product Unit")
    price_unit = fields.Float(string="Unit Price", digits="Product Price", readonly=True)
    discount = fields.Float(string="Disc.%", readonly=True)

    def _check_quantity(self):
        self.ensure_one()
        if not self.order_line_id:
            return
        if self.quantity < 0:
            raise UserError(_("Settlement quantity cannot be negative."))
        if self.quantity > self.remaining_qty:
            raise UserError(_("Settlement quantity cannot exceed remaining quantity for %s.") % self.product_id.display_name)


class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    def _prepare_picking_default_values(self):
        vals = super()._prepare_picking_default_values()
        if self.picking_id.tha_consignment_order_id:
            vals.update({
                "tha_is_consignment_transfer": True,
                "tha_consignment_order_id": self.picking_id.tha_consignment_order_id.id,
            })
        return vals
