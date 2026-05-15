from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ThaConsignmentSettlement(models.Model):
    _name = "tha.consignment.settlement"
    _inherit = "tha.consignment.mixin"
    _description = "Consignment Settlement"
    _order = "date_to desc, id desc"

    name = fields.Char(default=lambda self: _("New"), copy=False, readonly=True, index=True)
    partner_id = fields.Many2one("res.partner", string="Shop", domain=[("is_consignment_shop", "=", True)], required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self._default_consignment_company(), required=True)
    period_from = fields.Date(required=True)
    date_to = fields.Date(string="Period To", default=fields.Date.context_today, required=True)
    source_location_id = fields.Many2one("stock.location", string="Source Location", domain=[("usage", "=", "internal")], required=True)
    pricelist_id = fields.Many2one("product.pricelist", string="Pricelist")
    currency_id = fields.Many2one("res.currency", compute="_compute_currency_id", store=True, readonly=False, required=True)
    commission_rate = fields.Float(string="Commission %", default=0.0)
    state = fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed"), ("cancel", "Cancelled")], default="draft", copy=False, required=True)
    line_ids = fields.One2many("tha.consignment.settlement.line", "settlement_id", string="Settlement Lines", copy=True)
    picking_id = fields.Many2one("stock.picking", string="Stock Out", copy=False, readonly=True)
    invoice_id = fields.Many2one("account.move", string="Customer Invoice", copy=False, readonly=True)
    commission_bill_id = fields.Many2one("account.move", string="Commission Bill", copy=False, readonly=True)
    invoice_count = fields.Integer(compute="_compute_document_counts")
    commission_bill_count = fields.Integer(compute="_compute_document_counts")
    amount_total = fields.Monetary(compute="_compute_amounts", store=True)
    commission_amount = fields.Monetary(compute="_compute_amounts", store=True)
    net_amount = fields.Monetary(compute="_compute_amounts", store=True)

    @api.depends("pricelist_id", "company_id")
    def _compute_currency_id(self):
        for settlement in self:
            settlement.currency_id = settlement.pricelist_id.currency_id or settlement.company_id.currency_id

    @api.depends("line_ids.subtotal", "line_ids.commission_amount", "line_ids.net_amount")
    def _compute_amounts(self):
        for settlement in self:
            settlement.amount_total = sum(settlement.line_ids.mapped("subtotal"))
            settlement.commission_amount = sum(settlement.line_ids.mapped("commission_amount"))
            settlement.net_amount = sum(settlement.line_ids.mapped("net_amount"))

    @api.constrains("name", "company_id")
    def _check_unique_name(self):
        self._check_unique_consignment_name()

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    @api.depends("invoice_id", "commission_bill_id")
    def _compute_document_counts(self):
        for settlement in self:
            settlement.invoice_count = 1 if settlement.invoice_id else 0
            settlement.commission_bill_count = 1 if settlement.commission_bill_id else 0

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.source_location_id = self.partner_id.consignment_location_id
        self.pricelist_id = self.partner_id.consignment_pricelist_id
        self.commission_rate = self.partner_id.commission_rate
        for line in self.line_ids:
            line.commission_rate = self.commission_rate
            line._onchange_price_inputs()

    def action_confirm(self):
        for settlement in self:
            if settlement.state != "draft":
                continue
            settlement._check_can_confirm()
            settlement._assign_sequence()
            picking = settlement._create_stock_out()
            settlement.write({"picking_id": picking.id, "state": "confirmed"})
        return True

    def _assign_sequence(self):
        if not self.name or self.name in (_("New"), "New"):
            self.name = self._next_consignment_sequence(
                "tha.consignment.settlement",
                "tha_consignment_sale.seq_consignment_settlement",
                self.date_to,
            ) or _("New")

    def action_cancel(self):
        for settlement in self:
            if settlement.picking_id.state == "done":
                raise UserError(_("You cannot cancel %s because its stock out is done.") % settlement.display_name)
            linked_moves = settlement.invoice_id | settlement.commission_bill_id
            active_moves = linked_moves.filtered(lambda move: move.state != "cancel")
            if active_moves:
                raise UserError(_("Cancel the linked invoice/bill before cancelling %s.") % settlement.display_name)
            if settlement.picking_id and settlement.picking_id.state != "cancel":
                settlement.picking_id.action_cancel()
            settlement.state = "cancel"
        return True

    def unlink(self):
        for settlement in self:
            if settlement.state == "confirmed":
                raise UserError(_("Cancel %s before deleting it.") % settlement.display_name)
            if settlement.picking_id and settlement.picking_id.state not in ("cancel",):
                raise UserError(_("You cannot delete %s while it is linked to an active stock out.") % settlement.display_name)
            linked_moves = settlement.invoice_id | settlement.commission_bill_id
            if linked_moves.filtered(lambda move: move.state != "cancel"):
                raise UserError(_("You cannot delete %s while it is linked to an active invoice or bill.") % settlement.display_name)
        return super().unlink()

    def action_view_stock_out(self):
        self.ensure_one()
        return self._open_record("stock.picking", self.picking_id.id, _("Consignment Stock Out"))

    def action_view_invoice(self):
        self.ensure_one()
        return self._open_record("account.move", self.invoice_id.id, _("Customer Invoice"))

    def action_view_commission_bill(self):
        self.ensure_one()
        return self._open_record("account.move", self.commission_bill_id.id, _("Commission Bill"))

    def _open_record(self, model, res_id, name):
        return {"type": "ir.actions.act_window", "name": name, "res_model": model, "view_mode": "form", "res_id": res_id}

    def action_create_invoice(self):
        for settlement in self:
            if settlement.state != "confirmed":
                raise UserError(_("Confirm the settlement before creating an invoice."))
            if not settlement.invoice_id:
                settlement.invoice_id = settlement._create_customer_invoice()
        return True

    def action_create_commission_bill(self):
        for settlement in self:
            if settlement.state != "confirmed":
                raise UserError(_("Confirm the settlement before creating a bill."))
            if settlement.commission_amount and not settlement.commission_bill_id:
                settlement.commission_bill_id = settlement._create_commission_bill()
        return True

    def _check_can_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one sold product line."))
        if self.source_location_id.usage != "internal":
            raise UserError(_("Settlement source must be an internal consignment location."))
        for line in self.line_ids:
            line._check_positive_quantity()

    def _create_stock_out(self):
        self.ensure_one()
        customer_location = self._customer_location()
        picking_type = self._consignment_picking_type(
            "sold",
            _("Consignment Sold"),
            "outgoing",
            "CONSOLD",
            "tha_consignment_sale.seq_picking_consignment_sold",
            self.source_location_id,
            customer_location,
            self.company_id,
        )
        moves = [Command.create(line._prepare_stock_move_vals(customer_location)) for line in self.line_ids]
        picking = self.env["stock.picking"].with_company(self.company_id).create({
            "picking_type_id": picking_type.id,
            "partner_id": self.partner_id.id,
            "origin": self.name,
            "location_id": self.source_location_id.id,
            "location_dest_id": customer_location.id,
            "company_id": self.company_id.id,
            "tha_is_consignment_transfer": True,
            "tha_consignment_settlement_id": self.id,
            "move_ids": moves,
        })
        picking.action_confirm()
        picking.action_assign()
        return picking

    def _create_customer_invoice(self):
        self.ensure_one()
        invoice_lines = []
        for line in self.line_ids:
            invoice_lines.append(Command.create({
                "product_id": line.product_id.id,
                "name": line.product_id.display_name,
                "quantity": line.sold_qty,
                "product_uom_id": line.product_uom_id.id,
                "price_unit": line.price_unit,
                "discount": line.discount,
                "tax_ids": [Command.clear()],
            }))
        return self.env["account.move"].with_company(self.company_id).create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": self.date_to,
            "invoice_origin": self.name,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "invoice_line_ids": invoice_lines,
        })

    def _create_commission_bill(self):
        self.ensure_one()
        product = self.env.ref("tha_consignment_sale.product_consignment_commission")
        return self.env["account.move"].with_company(self.company_id).create({
            "move_type": "in_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": self.date_to,
            "invoice_origin": self.name,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "invoice_line_ids": [Command.create({
                "product_id": product.product_variant_id.id,
                "name": _("Consignment commission for %s") % self.name,
                "quantity": 1.0,
                "price_unit": self.commission_amount,
                "tax_ids": [Command.clear()],
            })],
        })


class ThaConsignmentSettlementLine(models.Model):
    _name = "tha.consignment.settlement.line"
    _description = "Consignment Settlement Line"
    _order = "settlement_id, sequence, id"

    sequence = fields.Integer(default=10)
    settlement_id = fields.Many2one("tha.consignment.settlement", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="settlement_id.company_id", store=True)
    currency_id = fields.Many2one(related="settlement_id.currency_id", store=True)
    product_id = fields.Many2one("product.product", string="Product", domain=[("type", "=", "consu")], required=True)
    product_uom_id = fields.Many2one("uom.uom", string="UoM", required=True)
    available_qty = fields.Float(string="Available Consignment Qty", compute="_compute_available_qty", digits="Product Unit")
    sold_qty = fields.Float(string="Sold Qty", default=1.0, digits="Product Unit", required=True)
    price_unit = fields.Monetary(string="Unit Price", required=True)
    discount = fields.Float(string="Discount %", default=0.0)
    commission_rate = fields.Float(string="Commission %")
    subtotal = fields.Monetary(compute="_compute_amounts", store=True)
    commission_amount = fields.Monetary(compute="_compute_amounts", store=True)
    net_amount = fields.Monetary(compute="_compute_amounts", store=True)

    @api.depends("product_id", "settlement_id.source_location_id")
    def _compute_available_qty(self):
        Quant = self.env["stock.quant"]
        for line in self:
            line.available_qty = Quant._get_available_quantity(line.product_id, line.settlement_id.source_location_id, strict=False) if line.product_id and line.settlement_id.source_location_id else 0.0

    @api.depends("sold_qty", "price_unit", "discount", "commission_rate")
    def _compute_amounts(self):
        for line in self:
            line.subtotal = line.sold_qty * line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.commission_amount = line.subtotal * line.commission_rate / 100.0
            line.net_amount = line.subtotal - line.commission_amount

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.product_uom_id = self.product_id.uom_id
        self.commission_rate = self.settlement_id.commission_rate
        self._onchange_price_inputs()

    @api.onchange("sold_qty", "product_uom_id")
    def _onchange_price_inputs(self):
        self.price_unit = self.settlement_id._price_from_pricelist(
            self.settlement_id.pricelist_id,
            self.product_id,
            self.sold_qty,
            self.product_uom_id,
            self.settlement_id.date_to,
        )

    @api.constrains("sold_qty", "discount", "commission_rate")
    def _check_values(self):
        for line in self:
            line._check_positive_quantity()
            if not 0 <= line.discount <= 100:
                raise ValidationError(_("Discount must be between 0 and 100."))
            if line.commission_rate < 0:
                raise ValidationError(_("Commission cannot be negative."))

    def _check_positive_quantity(self):
        if self.sold_qty <= 0:
            raise ValidationError(_("Sold quantity must be greater than zero."))

    def _prepare_stock_move_vals(self, customer_location):
        self.ensure_one()
        return {
            "description_picking": self.product_id.display_name,
            "product_id": self.product_id.id,
            "product_uom_qty": self.sold_qty,
            "product_uom": self.product_uom_id.id,
            "location_id": self.settlement_id.source_location_id.id,
            "location_dest_id": customer_location.id,
            "company_id": self.settlement_id.company_id.id,
            "origin": self.settlement_id.name,
            "tha_consignment_settlement_line_id": self.id,
        }
