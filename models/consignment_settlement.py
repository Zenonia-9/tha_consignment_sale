from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ThaConsignmentSettlement(models.Model):
    _name = "tha.consignment.settlement"
    _inherit = "tha.consignment.mixin"
    _description = "Consignment Settlement"
    _order = "create_date desc, id desc"

    name = fields.Char(default=lambda self: _("New"), copy=False, readonly=True, index=True)
    order_id = fields.Many2one("tha.consignment.order", string="Consignment Order", ondelete="restrict")
    partner_id = fields.Many2one("res.partner", string="Customer", required=True)
    partner_invoice_id = fields.Many2one("res.partner", string="Invoice Address")
    company_id = fields.Many2one("res.company", required=True)
    settlement_date = fields.Date(default=fields.Date.context_today, required=True)
    pricelist_id = fields.Many2one("product.pricelist", string="Pricelist", default=lambda self: self._default_pricelist())
    journal_id = fields.Many2one(
        "account.journal",
        string="Invoicing Journal",
        domain="[('type', '=', 'sale'), ('company_id', '=', company_id)]",
        check_company=True,
        default=lambda self: self._default_sale_journal(),
    )
    currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_currency_id",
        store=True,
        readonly=False,
        required=True,
        default=lambda self: self._default_currency(),
    )
    commission_rate = fields.Float(string="Commission %", default=0.0)
    user_id = fields.Many2one("res.users", string="Salesperson", check_company=True)
    team_id = fields.Many2one(
        "crm.team",
        string="Sales Team",
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    payment_term_id = fields.Many2one("account.payment.term", string="Payment Terms", check_company=True)
    fiscal_position_id = fields.Many2one("account.fiscal.position", string="Fiscal Position", check_company=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", check_company=True)
    source_location_id = fields.Many2one("stock.location", string="Source Location")
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("cancel", "Cancelled")],
        default="draft",
        required=True,
        copy=False,
    )
    line_ids = fields.One2many("tha.consignment.settlement.line", "settlement_id", string="Settlement Lines", copy=True)
    picking_id = fields.Many2one("stock.picking", string="Delivery", copy=False, readonly=True)
    delivery_status = fields.Selection(related="picking_id.state", string="Delivery Status")
    effective_date = fields.Datetime(string="Effective Date", compute="_compute_effective_date")
    invoice_id = fields.Many2one("account.move", string="Customer Invoice", copy=False, readonly=True)
    commission_bill_id = fields.Many2one("account.move", string="Commission Bill", copy=False, readonly=True)
    invoice_status = fields.Selection(
        [("invoiced", "Fully Invoiced"), ("to invoice", "To Invoice"), ("no", "Nothing to Invoice")],
        string="Invoice Status",
        compute="_compute_invoice_status",
        store=True,
    )
    invoice_count = fields.Integer(compute="_compute_document_counts")
    commission_bill_count = fields.Integer(compute="_compute_document_counts")
    amount_total = fields.Monetary(compute="_compute_amounts", store=True)
    commission_amount = fields.Monetary(compute="_compute_amounts", store=True)
    net_amount = fields.Monetary(compute="_compute_amounts", store=True)

    @api.depends("pricelist_id", "company_id")
    def _compute_currency_id(self):
        for settlement in self:
            settlement.currency_id = settlement.pricelist_id.currency_id or settlement.company_id.currency_id

    @api.depends("line_ids.subtotal", "line_ids.commission_amount", "line_ids.net_amount", "line_ids.display_type")
    def _compute_amounts(self):
        for settlement in self:
            product_lines = settlement.line_ids.filtered(lambda line: not line.display_type)
            settlement.amount_total = sum(product_lines.mapped("subtotal"))
            settlement.commission_amount = sum(product_lines.mapped("commission_amount"))
            settlement.net_amount = sum(product_lines.mapped("net_amount"))

    def _compute_effective_date(self):
        for settlement in self:
            settlement.effective_date = settlement.picking_id.date_done

    @api.depends("state", "invoice_id.state")
    def _compute_invoice_status(self):
        for settlement in self:
            if settlement.state != "confirmed":
                settlement.invoice_status = "no"
            elif settlement.invoice_id and settlement.invoice_id.state != "cancel":
                settlement.invoice_status = "invoiced"
            else:
                settlement.invoice_status = "to invoice"

    @api.depends("invoice_id", "commission_bill_id")
    def _compute_document_counts(self):
        for settlement in self:
            settlement.invoice_count = 1 if settlement.invoice_id else 0
            settlement.commission_bill_count = 1 if settlement.commission_bill_id else 0

    @api.constrains("name", "company_id")
    def _check_unique_name(self):
        self._check_unique_consignment_name()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
            order = self.env["tha.consignment.order"].browse(vals.get("order_id")) if vals.get("order_id") else self.env["tha.consignment.order"]
            partner = self.env["res.partner"].browse(vals.get("partner_id")) if vals.get("partner_id") else self.env["res.partner"]
            pricelist = (
                self.env["product.pricelist"].browse(vals["pricelist_id"])
                if vals.get("pricelist_id")
                else order.pricelist_id or partner.consignment_pricelist_id or self._default_pricelist(company=company)
            )
            if pricelist and not vals.get("pricelist_id"):
                vals["pricelist_id"] = pricelist.id
            if not vals.get("currency_id"):
                vals["currency_id"] = (pricelist.currency_id or company.currency_id).id
        settlements = super().create(vals_list)
        for settlement in settlements:
            if not settlement.name or settlement.name in (_("New"), "New"):
                settlement._assign_sequence()
        return settlements

    def _default_pricelist(self, company=False, partner=False):
        company = company or self.env.company
        partner = partner or self.env["res.partner"]
        return (
            partner.consignment_pricelist_id
            or self.env["product.pricelist"].search([
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ], limit=1)
        )

    def _default_currency(self, company=False, pricelist=False):
        company = company or self.env.company
        pricelist = pricelist or self._default_pricelist(company=company)
        return pricelist.currency_id or company.currency_id

    def _default_sale_journal(self, company=False):
        company = company or self.env.company
        return self.env["account.journal"].search([
            ("type", "=", "sale"),
            ("company_id", "=", company.id),
        ], order="sequence, id", limit=1)

    @api.onchange("order_id")
    def _onchange_order_id(self):
        for settlement in self:
            order = settlement.order_id
            if not order:
                continue
            invoice_partner = order._prepare_invoice_partner(order.partner_id)
            settlement.partner_id = order.partner_id
            settlement.partner_invoice_id = invoice_partner
            settlement.company_id = order.company_id
            settlement.pricelist_id = order.pricelist_id
            settlement.journal_id = settlement._default_sale_journal(company=order.company_id)
            settlement.commission_rate = order.commission_rate
            settlement.user_id = order.user_id
            settlement.team_id = order.team_id
            settlement.payment_term_id = order.partner_id.property_payment_term_id
            settlement.fiscal_position_id = (
                self.env["account.fiscal.position"]._get_fiscal_position(order.partner_id, invoice_partner)
                if hasattr(self.env["account.fiscal.position"], "_get_fiscal_position")
                else self.env["account.fiscal.position"]
            )
            settlement.warehouse_id = order.destination_warehouse_id
            settlement.source_location_id = order.destination_location_id
            settlement.currency_id = settlement.pricelist_id.currency_id or settlement.company_id.currency_id

    @api.onchange("pricelist_id")
    def _onchange_pricelist_id(self):
        self.currency_id = self.pricelist_id.currency_id or self.company_id.currency_id

    def _assign_sequence(self):
        if not self.name or self.name in (_("New"), "New"):
            self.name = self._next_consignment_sequence(
                "tha.consignment.settlement",
                "tha_consignment_sale.seq_consignment_settlement",
                self.settlement_date,
            ) or _("New")

    def action_confirm(self):
        for settlement in self:
            if settlement.state != "draft":
                continue
            settlement._check_can_confirm()
            settlement._assign_sequence()
            picking = settlement._create_stock_out()
            settlement.write({"picking_id": picking.id, "state": "confirmed"})
        return True

    def action_cancel(self):
        for settlement in self:
            if settlement.picking_id.state == "done":
                raise UserError(_("You cannot cancel %s because its delivery is done.") % settlement.display_name)
            active_moves = (settlement.invoice_id | settlement.commission_bill_id).filtered(lambda move: move.state != "cancel")
            if active_moves:
                raise UserError(_("Cancel the linked invoice and bill before cancelling %s.") % settlement.display_name)
            if settlement.picking_id and settlement.picking_id.state != "cancel":
                settlement.picking_id.action_cancel()
            settlement.state = "cancel"
        return True

    def unlink(self):
        for settlement in self:
            if settlement.state == "confirmed":
                raise UserError(_("Cancel %s before deleting it.") % settlement.display_name)
            if settlement.picking_id and settlement.picking_id.state not in ("cancel",):
                raise UserError(_("You cannot delete %s while it is linked to an active delivery.") % settlement.display_name)
            active_moves = (settlement.invoice_id | settlement.commission_bill_id).filtered(lambda move: move.state != "cancel")
            if active_moves:
                raise UserError(_("You cannot delete %s while it is linked to an active invoice or bill.") % settlement.display_name)
        return super().unlink()

    def action_view_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consignment Order"),
            "res_model": "tha.consignment.order",
            "view_mode": "form",
            "res_id": self.order_id.id,
        }

    def action_view_delivery(self):
        self.ensure_one()
        return self._open_record("stock.picking", self.picking_id.id, _("Delivery"))

    def action_view_invoice(self):
        self.ensure_one()
        return self._open_account_move(self.invoice_id, "out_invoice")

    def action_view_commission_bill(self):
        self.ensure_one()
        return self._open_account_move(self.commission_bill_id, "in_invoice")

    def _open_account_move(self, move, move_type):
        if not move:
            return {"type": "ir.actions.act_window_close"}
        action_xmlid = "account.action_move_out_invoice_type" if move_type == "out_invoice" else "account.action_move_in_invoice_type"
        action = self.env["ir.actions.actions"]._for_xml_id(action_xmlid)
        action["res_id"] = move.id
        action["views"] = [(self.env.ref("account.view_move_form").id, "form")]
        action["view_mode"] = "form"
        return action

    def _open_record(self, model, res_id, name):
        if not res_id:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "form",
            "res_id": res_id,
        }

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != "confirmed":
            raise UserError(_("Confirm the settlement before creating an invoice."))
        if self.invoice_id and self.invoice_id.state != "cancel":
            return self.action_view_invoice()
        self.invoice_id = self._create_customer_invoice()
        return self.action_view_invoice()

    def action_create_commission_bill(self):
        self.ensure_one()
        if self.state != "confirmed":
            raise UserError(_("Confirm the settlement before creating a bill."))
        if not self.commission_amount:
            raise UserError(_("There is no commission amount to bill."))
        if self.commission_bill_id and self.commission_bill_id.state != "cancel":
            return self.action_view_commission_bill()
        self.commission_bill_id = self._create_commission_bill()
        return self.action_view_commission_bill()

    def _check_can_confirm(self):
        self.ensure_one()
        if not self.order_id:
            raise UserError(_("A settlement must be linked to a consignment order."))
        if not self.partner_invoice_id:
            raise UserError(_("An invoice address is required before confirming a settlement."))
        if not self.warehouse_id or not self.source_location_id:
            raise UserError(_("Warehouse and source location are required before confirming a settlement."))
        product_lines = self.line_ids.filtered(lambda line: not line.display_type)
        if not product_lines:
            raise UserError(_("Add at least one settlement product line."))
        if self.source_location_id.usage != "internal":
            raise UserError(_("Settlement source must be an internal consignment location."))
        for line in product_lines:
            line._check_positive_quantity()
            line._check_available_quantity()

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
        moves = [
            Command.create(line._prepare_stock_move_vals(customer_location))
            for line in self.line_ids.filtered(lambda settlement_line: not settlement_line.display_type)
        ]
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
        invoice_lines = [
            Command.create({
                "product_id": line.product_id.id,
                "name": line.name or line.product_id.display_name,
                "quantity": line.product_uom_qty,
                "product_uom_id": line.product_uom_id.id,
                "price_unit": line.price_unit,
                "discount": line.discount,
                "tax_ids": [Command.clear()],
            })
            for line in self.line_ids.filtered(lambda settlement_line: not settlement_line.display_type)
        ]
        return self.env["account.move"].with_company(self.company_id).create({
            "move_type": "out_invoice",
            "partner_id": self.partner_invoice_id.id or self.partner_id.id,
            "partner_shipping_id": self.partner_id.id,
            "invoice_date": self.settlement_date,
            "invoice_origin": self.name,
            "invoice_payment_term_id": self.payment_term_id.id,
            "fiscal_position_id": self.fiscal_position_id.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "journal_id": self.journal_id.id,
            "team_id": self.team_id.id,
            "invoice_user_id": self.user_id.id,
            "user_id": self.user_id.id,
            "tha_consignment_settlement_id": self.id,
            "invoice_line_ids": invoice_lines,
        })

    def _create_commission_bill(self):
        self.ensure_one()
        product = self.env.ref("tha_consignment_sale.product_consignment_commission")
        return self.env["account.move"].with_company(self.company_id).create({
            "move_type": "in_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": self.settlement_date,
            "invoice_origin": self.name,
            "invoice_payment_term_id": self.payment_term_id.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "tha_consignment_settlement_id": self.id,
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

    settlement_id = fields.Many2one("tha.consignment.settlement", required=True, ondelete="cascade")
    order_line_id = fields.Many2one(
        "tha.consignment.order.line",
        string="Order Line",
        domain="[('order_id', '=', settlement_id.order_id), ('display_type', '=', False)]",
        ondelete="restrict",
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related="settlement_id.company_id", store=True)
    currency_id = fields.Many2one(related="settlement_id.currency_id", store=True)
    display_type = fields.Selection(
        selection=[
            ("line_section", "Section"),
            ("line_note", "Note"),
        ],
        default=False,
    )
    product_id = fields.Many2one("product.product", string="Product Variant", domain=[("type", "=", "consu")])
    product_template_id = fields.Many2one(
        "product.template",
        string="Product",
        compute="_compute_product_template_id",
        readonly=False,
        search="_search_product_template_id",
        domain=lambda self: self._fields["product_id"]._description_domain(self.env),
    )
    name = fields.Text(string="Description")
    product_uom_qty = fields.Float(string="Quantity", default=1.0, digits="Product Unit")
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        domain='[("id", "in", allowed_uom_ids)]',
    )
    allowed_uom_ids = fields.Many2many("uom.uom", compute="_compute_allowed_uom_ids")
    available_qty = fields.Float(string="Available Qty", compute="_compute_available_qty", digits="Product Unit")
    price_unit = fields.Monetary(string="Unit Price")
    discount = fields.Float(string="Disc.%", default=0.0)
    commission_rate = fields.Float(string="Commission %", default=0.0)
    subtotal = fields.Monetary(string="Subtotal", compute="_compute_amounts", store=True)
    commission_amount = fields.Monetary(string="Commission Amount", compute="_compute_amounts", store=True)
    net_amount = fields.Monetary(string="Net Amount", compute="_compute_amounts", store=True)

    @api.depends("product_id", "product_id.uom_id", "product_id.uom_ids")
    def _compute_allowed_uom_ids(self):
        for line in self:
            line.allowed_uom_ids = line.product_id.uom_id | line.product_id.uom_ids

    @api.depends("product_id")
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [("product_id.product_tmpl_id", operator, value)]

    @api.depends("product_id", "settlement_id.source_location_id")
    def _compute_available_qty(self):
        Quant = self.env["stock.quant"]
        for line in self:
            if line.display_type or not line.product_id or not line.settlement_id.source_location_id:
                line.available_qty = 0.0
                continue
            line.available_qty = Quant._get_available_quantity(
                line.product_id,
                line.settlement_id.source_location_id,
                strict=False,
            )

    @api.depends("product_uom_qty", "price_unit", "discount", "settlement_id.commission_rate", "display_type")
    def _compute_amounts(self):
        for line in self:
            if line.display_type:
                line.subtotal = 0.0
                line.commission_amount = 0.0
                line.net_amount = 0.0
                continue
            line.subtotal = line.product_uom_qty * line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.commission_amount = line.subtotal * (line.settlement_id.commission_rate or 0.0) / 100.0
            line.net_amount = line.subtotal - line.commission_amount

    @api.onchange("order_line_id")
    def _onchange_order_line_id(self):
        if not self.order_line_id:
            return
        self.product_id = self.order_line_id.product_id
        self.name = self.order_line_id.name
        self.product_uom_id = self.order_line_id.product_uom_id
        self.price_unit = self.order_line_id.consignment_price_unit
        self.discount = self.order_line_id.consignment_discount
    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.display_type:
            return
        self.name = self.product_id.display_name
        self.product_uom_id = self.product_id.uom_id
        self._onchange_price_inputs()

    @api.onchange("product_template_id")
    def _onchange_product_template_id(self):
        if self.display_type or not self.product_template_id:
            return
        if self.product_id.product_tmpl_id != self.product_template_id:
            self.product_id = self.product_template_id.product_variant_id

    @api.onchange("product_uom_qty", "product_uom_id", "product_id")
    def _onchange_price_inputs(self):
        if self.display_type or not self.product_id:
            return
        self.price_unit = self.settlement_id._price_from_pricelist(
            self.settlement_id.pricelist_id,
            self.product_id,
            self.product_uom_qty,
            self.product_uom_id,
            self.settlement_id.settlement_date,
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("display_type"):
                vals.update({
                    "order_line_id": False,
                    "product_id": False,
                    "product_uom_id": False,
                    "product_uom_qty": 0.0,
                    "price_unit": 0.0,
                    "discount": 0.0,
                })
        return super().create(vals_list)

    def write(self, vals):
        if "display_type" in vals and self.filtered(lambda line: line.display_type != vals.get("display_type")):
            raise UserError(_("You cannot change the type of a settlement line. Delete it and create a new one instead."))
        return super().write(vals)

    @api.constrains("display_type", "product_id", "product_uom_id", "product_uom_qty", "discount")
    def _check_values(self):
        for line in self:
            if not line.name:
                raise ValidationError(_("Description is required on settlement lines."))
            if line.display_type:
                if line.product_id or line.product_uom_id:
                    raise ValidationError(_("Section and note lines cannot have a product or unit."))
                continue
            if not line.product_id or not line.product_uom_id:
                raise ValidationError(_("Product and unit are required on settlement product lines."))
            line._check_positive_quantity()
            if not 0 <= line.discount <= 100:
                raise ValidationError(_("Discount must be between 0 and 100."))

    def _check_positive_quantity(self):
        if self.product_uom_qty <= 0:
            raise ValidationError(_("Quantity must be greater than zero."))

    def _requested_qty_in_product_uom(self):
        self.ensure_one()
        if not self.product_id:
            return 0.0
        if self.product_uom_id:
            return self.product_uom_id._compute_quantity(self.product_uom_qty, self.product_id.uom_id)
        return self.product_uom_qty

    def _has_available_quantity(self):
        self.ensure_one()
        if self.display_type or not self.product_id or not self.settlement_id.source_location_id:
            return True
        return float_compare(
            self.available_qty,
            self._requested_qty_in_product_uom(),
            precision_rounding=self.product_id.uom_id.rounding,
        ) >= 0

    def _check_available_quantity(self):
        self.ensure_one()
        if not self._has_available_quantity():
            raise UserError(
                _("Not enough consignment stock for %s in %s.")
                % (self.product_id.display_name, self.settlement_id.source_location_id.display_name)
            )

    def _prepare_stock_move_vals(self, customer_location):
        self.ensure_one()
        return {
            "description_picking": self.name or self.product_id.display_name,
            "product_id": self.product_id.id,
            "product_uom_qty": self.product_uom_qty,
            "product_uom": self.product_uom_id.id,
            "location_id": self.settlement_id.source_location_id.id,
            "location_dest_id": customer_location.id,
            "company_id": self.settlement_id.company_id.id,
            "origin": self.settlement_id.name,
            "tha_consignment_settlement_line_id": self.id,
        }
