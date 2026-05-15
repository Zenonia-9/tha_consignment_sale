from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ThaConsignmentReturn(models.Model):
    _name = "tha.consignment.return"
    _inherit = "tha.consignment.mixin"
    _description = "Consignment Return"
    _order = "date_return desc, id desc"

    name = fields.Char(default=lambda self: _("New"), copy=False, readonly=True, index=True)
    date_return = fields.Date(string="Return Date", default=fields.Date.context_today, required=True)
    partner_id = fields.Many2one("res.partner", string="Shop", domain=[("is_consignment_shop", "=", True)], required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self._default_consignment_company(), required=True)
    source_location_id = fields.Many2one("stock.location", string="Source Location", domain=[("usage", "=", "internal")], required=True)
    destination_warehouse_id = fields.Many2one(
        "stock.warehouse",
        default=lambda self: self._default_source_warehouse(),
        check_company=True,
        domain=[("tha_is_consignment_source_warehouse", "=", True)],
    )
    destination_location_id = fields.Many2one("stock.location", string="Destination Location", required=True, default=lambda self: self._default_source_warehouse().lot_stock_id)
    state = fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed"), ("cancel", "Cancelled")], default="draft", copy=False, required=True)
    line_ids = fields.One2many("tha.consignment.return.line", "return_id", string="Return Lines", copy=True)
    picking_id = fields.Many2one("stock.picking", string="Return Transfer", copy=False, readonly=True)
    picking_state = fields.Selection(related="picking_id.state", string="Transfer Status")

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.source_location_id = self.partner_id.consignment_location_id

    @api.onchange("destination_warehouse_id")
    def _onchange_destination_warehouse_id(self):
        self.destination_location_id = self.destination_warehouse_id.lot_stock_id

    def action_confirm(self):
        for consignment_return in self:
            if consignment_return.state != "draft":
                continue
            consignment_return._check_can_confirm()
            consignment_return._assign_sequence()
            picking = consignment_return._create_return_picking()
            consignment_return.write({"picking_id": picking.id, "state": "confirmed"})
        return True

    def _assign_sequence(self):
        if not self.name or self.name in (_("New"), "New"):
            self.name = self.env["ir.sequence"].next_by_code("tha.consignment.return") or _("New")

    @api.model
    def _fix_missing_sequences(self):
        for consignment_return in self.search([("name", "in", [False, "New"]), ("state", "!=", "draft")], order="id"):
            consignment_return._assign_sequence()
        return True

    def action_cancel(self):
        for consignment_return in self:
            if consignment_return.picking_id.state == "done":
                raise UserError(_("You cannot cancel %s because its transfer is done.") % consignment_return.display_name)
            if consignment_return.picking_id and consignment_return.picking_id.state != "cancel":
                consignment_return.picking_id.action_cancel()
            consignment_return.state = "cancel"
        return True

    def unlink(self):
        for consignment_return in self:
            if consignment_return.state == "confirmed":
                raise UserError(_("Cancel %s before deleting it.") % consignment_return.display_name)
            if consignment_return.picking_id and consignment_return.picking_id.state not in ("cancel",):
                raise UserError(_("You cannot delete %s while it is linked to an active transfer.") % consignment_return.display_name)
        return super().unlink()

    def action_view_transfer(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Consignment Return Transfer"), "res_model": "stock.picking", "view_mode": "form", "res_id": self.picking_id.id}

    def _check_can_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one returned product line."))
        if self.source_location_id.usage != "internal" or self.destination_location_id.usage != "internal":
            raise UserError(_("Consignment returns must move between internal locations."))
        for line in self.line_ids:
            line._check_positive_quantity()

    def _create_return_picking(self):
        self.ensure_one()
        picking_type = self._consignment_picking_type(
            "return",
            _("Consignment Return"),
            "internal",
            "CONRET",
            "tha_consignment_sale.seq_picking_consignment_return",
            self.source_location_id,
            self.destination_location_id,
            self.company_id,
        )
        moves = [Command.create(line._prepare_stock_move_vals()) for line in self.line_ids]
        picking = self.env["stock.picking"].with_company(self.company_id).create({
            "picking_type_id": picking_type.id,
            "partner_id": self.partner_id.id,
            "origin": self.name,
            "location_id": self.source_location_id.id,
            "location_dest_id": self.destination_location_id.id,
            "company_id": self.company_id.id,
            "tha_is_consignment_transfer": True,
            "tha_consignment_return_id": self.id,
            "move_ids": moves,
        })
        picking.move_ids._action_confirm(merge=False)
        picking.action_assign()
        return picking


class ThaConsignmentReturnLine(models.Model):
    _name = "tha.consignment.return.line"
    _description = "Consignment Return Line"
    _order = "return_id, sequence, id"

    sequence = fields.Integer(default=10)
    return_id = fields.Many2one("tha.consignment.return", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="return_id.company_id", store=True)
    available_product_ids = fields.Many2many("product.product", compute="_compute_available_product_ids")
    product_id = fields.Many2one("product.product", string="Product", domain=[("id", "in", available_product_ids)], required=True)
    product_uom_qty = fields.Float(string="Quantity", default=1.0, digits="Product Unit", required=True)
    product_uom_id = fields.Many2one("uom.uom", string="UoM", required=True)

    @api.depends("return_id.source_location_id")
    def _compute_available_product_ids(self):
        Quant = self.env["stock.quant"]
        for line in self:
            quants = Quant.search([("location_id", "child_of", line.return_id.source_location_id.id), ("quantity", ">", 0)]) if line.return_id.source_location_id else Quant
            line.available_product_ids = quants.mapped("product_id")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.product_uom_id = self.product_id.uom_id

    @api.constrains("product_uom_qty")
    def _check_values(self):
        for line in self:
            line._check_positive_quantity()

    def _check_positive_quantity(self):
        if self.product_uom_qty <= 0:
            raise ValidationError(_("Quantity must be greater than zero."))

    def _prepare_stock_move_vals(self):
        self.ensure_one()
        return {
            "description_picking": self.product_id.display_name,
            "product_id": self.product_id.id,
            "product_uom_qty": self.product_uom_qty,
            "product_uom": self.product_uom_id.id,
            "location_id": self.return_id.source_location_id.id,
            "location_dest_id": self.return_id.destination_location_id.id,
            "company_id": self.return_id.company_id.id,
            "origin": self.return_id.name,
            "tha_consignment_return_line_id": self.id,
        }
