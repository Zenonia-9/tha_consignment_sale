from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ThaConsignmentOrder(models.Model):
    _name = "tha.consignment.order"
    _inherit = "tha.consignment.mixin"
    _description = "Consignment Order"
    _order = "create_date desc, id desc"

    name = fields.Char(default=lambda self: _("New"), copy=False, readonly=True, index=True)
    date_order = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    partner_id = fields.Many2one("res.partner", string="Shop", domain=[("is_consignment_shop", "=", True)], required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self._default_consignment_company(), required=True)
    source_warehouse_id = fields.Many2one(
        "stock.warehouse",
        default=lambda self: self._default_source_warehouse(),
        check_company=True,
        domain=[("tha_is_consignment_source_warehouse", "=", True)],
    )
    source_location_id = fields.Many2one("stock.location", default=lambda self: self._default_source_warehouse().lot_stock_id, required=True)
    destination_warehouse_id = fields.Many2one(
        "stock.warehouse",
        default=lambda self: self._default_destination_warehouse(),
        check_company=True,
        domain=[("tha_is_consignment_warehouse", "=", True)],
    )
    destination_location_id = fields.Many2one("stock.location", string="Destination Location", domain=[("usage", "=", "internal")], required=True)
    pricelist_id = fields.Many2one("product.pricelist", string="Pricelist")
    currency_id = fields.Many2one("res.currency", compute="_compute_currency_id", store=True, readonly=False, required=True)
    commission_rate = fields.Float(string="Commission %", default=0.0)
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("cancel", "Cancelled")],
        default="draft",
        required=True,
        copy=False,
    )
    picking_id = fields.Many2one("stock.picking", string="Related Transfer", copy=False, readonly=True)
    picking_state = fields.Selection(related="picking_id.state", string="Primary Transfer Status")
    picking_ids = fields.One2many("stock.picking", "tha_consignment_order_id", string="Transfer Records")
    transfer_count = fields.Integer(compute="_compute_transfer_summary", store=True, string="Transfers")
    open_transfer_count = fields.Integer(compute="_compute_transfer_summary", store=True, string="Open Transfers")
    transfer_state = fields.Selection(
        [
            ("no_transfer", "No Transfer"),
            ("draft", "Draft"),
            ("waiting", "Waiting"),
            ("confirmed", "Waiting"),
            ("assigned", "Ready"),
            ("partially_done", "Partially Done"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        compute="_compute_transfer_summary",
        store=True,
        string="Transfer Status",
    )
    line_ids = fields.One2many("tha.consignment.order.line", "order_id", string="Order Lines", copy=True)
    amount_total = fields.Monetary(compute="_compute_amounts", store=True)
    commission_amount = fields.Monetary(compute="_compute_amounts", store=True)
    net_amount = fields.Monetary(compute="_compute_amounts", store=True)

    @api.depends("pricelist_id", "company_id")
    def _compute_currency_id(self):
        for order in self:
            order.currency_id = order.pricelist_id.currency_id or order.company_id.currency_id

    @api.depends("line_ids.consignment_subtotal", "line_ids.commission_rate")
    def _compute_amounts(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped("consignment_subtotal"))
            order.commission_amount = sum(line.consignment_subtotal * line.commission_rate / 100.0 for line in order.line_ids)
            order.net_amount = order.amount_total - order.commission_amount

    @api.depends("picking_ids", "picking_ids.state")
    def _compute_transfer_summary(self):
        active_states = ("draft", "waiting", "confirmed", "assigned")
        state_priority = {
            "assigned": 4,
            "confirmed": 3,
            "waiting": 2,
            "draft": 1,
        }
        for order in self:
            pickings = order.picking_ids
            states = pickings.mapped("state")
            order.transfer_count = len(pickings)
            order.open_transfer_count = len(pickings.filtered(lambda picking: picking.state in active_states))
            if not states:
                order.transfer_state = "no_transfer"
            elif all(state == "cancel" for state in states):
                order.transfer_state = "cancel"
            elif all(state in ("done", "cancel") for state in states) and "done" in states:
                order.transfer_state = "done"
            elif "done" in states:
                order.transfer_state = "partially_done"
            else:
                order.transfer_state = max(states, key=lambda state: state_priority.get(state, 0))

    @api.constrains("name", "company_id")
    def _check_unique_name(self):
        self._check_unique_consignment_name()

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            if not order.name or order.name in (_("New"), "New"):
                order._assign_sequence()
        return orders

    @api.onchange("company_id")
    def _onchange_company_id(self):
        source_wh = self._find_flagged_warehouse("tha_is_consignment_source_warehouse", self.company_id)
        dest_wh = self._find_flagged_warehouse("tha_is_consignment_warehouse", self.company_id)
        self.source_warehouse_id = source_wh
        self.source_location_id = source_wh.lot_stock_id
        self.destination_warehouse_id = dest_wh

    @api.onchange("source_warehouse_id")
    def _onchange_source_warehouse_id(self):
        self.source_location_id = self.source_warehouse_id.lot_stock_id

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.destination_location_id = self.partner_id.consignment_location_id
        self.pricelist_id = self.partner_id.consignment_pricelist_id
        self.commission_rate = self.partner_id.commission_rate
        self.destination_warehouse_id = self._warehouse_for_location(self.destination_location_id, self.company_id) or self.destination_warehouse_id
        for line in self.line_ids:
            line.commission_rate = self.commission_rate
            line._onchange_price_inputs()

    def action_confirm(self):
        for order in self:
            if order.state != "draft":
                continue
            order._check_can_confirm()
            order._assign_sequence()
            picking = order._create_issue_picking()
            order.write({"picking_id": picking.id, "state": "confirmed"})
        return True

    def _assign_sequence(self):
        if not self.name or self.name in (_("New"), "New"):
            self.name = self._next_consignment_sequence(
                "tha.consignment.order",
                "tha_consignment_sale.seq_consignment_order",
                self.date_order,
            ) or _("New")

    def action_cancel(self):
        for order in self:
            done_pickings = order.picking_ids.filtered(lambda picking: picking.state == "done")
            if done_pickings:
                raise UserError(_("You cannot cancel %s because at least one transfer is done.") % order.display_name)
            pickings_to_cancel = order.picking_ids.filtered(lambda picking: picking.state != "cancel")
            if pickings_to_cancel:
                pickings_to_cancel.action_cancel()
            order.state = "cancel"
        return True

    def unlink(self):
        for order in self:
            if order.state == "confirmed":
                raise UserError(_("Cancel %s before deleting it.") % order.display_name)
            active_pickings = order.picking_ids.filtered(lambda picking: picking.state != "cancel")
            if active_pickings:
                raise UserError(_("You cannot delete %s while it is linked to an active transfer.") % order.display_name)
        return super().unlink()

    def action_view_transfer(self):
        self.ensure_one()
        if not self.picking_ids:
            return {"type": "ir.actions.act_window_close"}
        if len(self.picking_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Consignment Transfer"),
                "res_model": "stock.picking",
                "view_mode": "form",
                "res_id": self.picking_ids.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Consignment Transfers"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", self.picking_ids.ids)],
            "context": {"create": False},
        }

    def _validate_print_selection(self):
        orders = self.exists()
        if not orders:
            raise UserError(_("No consignment orders selected."))

        if any(order.state != "confirmed" for order in orders):
            raise UserError(_("Only confirmed consignment orders can be printed."))

        if any(not order.line_ids for order in orders):
            raise UserError(_("Each selected consignment order must have at least one product line."))

        company = orders[0].company_id
        if any(order.company_id != company for order in orders):
            raise UserError(_("Selected consignment orders must belong to the same company."))

        if any(not order.currency_id for order in orders):
            raise UserError(_("Each selected consignment order must have a currency."))

        if any(line.product_uom_qty <= 0 for order in orders for line in order.line_ids):
            raise UserError(_("Product quantities must be greater than zero before printing."))

        if any(line.consignment_price_unit < 0 for order in orders for line in order.line_ids):
            raise UserError(_("Unit price cannot be negative before printing."))

        return orders

    def action_open_print_wizard(self):
        orders = self._validate_print_selection()
        return {
            "type": "ir.actions.act_window",
            "name": _("Print Consignment Order"),
            "res_model": "tha.consignment.order.print.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_ids": orders.ids,
                "active_model": "tha.consignment.order",
            },
        }

    def _check_can_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one product line."))
        if not self.source_location_id or not self.destination_location_id:
            raise UserError(_("Source and destination locations are required."))
        if self.source_location_id == self.destination_location_id:
            raise UserError(_("Source and destination locations must be different."))
        if self.destination_location_id.usage != "internal":
            raise UserError(_("Consignment destination must be an internal location."))
        for line in self.line_ids:
            line._check_positive_quantity()

    def _create_issue_picking(self):
        self.ensure_one()
        picking_type = self._consignment_picking_type(
            "issue",
            _("Consignment Issue"),
            "internal",
            "CONISS",
            "tha_consignment_sale.seq_picking_consignment_issue",
            self.source_location_id,
            self.destination_location_id,
            self.company_id,
        )
        move_commands = []
        for line in self.line_ids:
            move_commands.append(Command.create(line._prepare_stock_move_vals()))
        picking = self.env["stock.picking"].with_company(self.company_id).create({
            "picking_type_id": picking_type.id,
            "partner_id": self.partner_id.id,
            "origin": self.name,
            "location_id": self.source_location_id.id,
            "location_dest_id": self.destination_location_id.id,
            "company_id": self.company_id.id,
            "tha_is_consignment_transfer": True,
            "tha_consignment_order_id": self.id,
            "move_ids": move_commands,
        })
        picking.move_ids._action_confirm(merge=False)
        picking.action_assign()
        return picking


class ThaConsignmentOrderLine(models.Model):
    _name = "tha.consignment.order.line"
    _description = "Consignment Order Line"
    _order = "order_id, sequence, id"

    sequence = fields.Integer(default=10)
    order_id = fields.Many2one("tha.consignment.order", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id", store=True)
    product_id = fields.Many2one(
        "product.product",
        string="Product Variant",
        domain=[("type", "=", "consu")],
        required=True,
    )
    product_template_id = fields.Many2one(
        "product.template",
        string="Product",
        compute="_compute_product_template_id",
        readonly=False,
        search="_search_product_template_id",
        domain=lambda self: self._fields["product_id"]._description_domain(self.env),
    )
    name = fields.Char(string="Description")
    product_uom_qty = fields.Float(string="Quantity", default=1.0, digits="Product Unit", required=True)
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        domain='[("id", "in", allowed_uom_ids)]',
        required=True,
    )
    allowed_uom_ids = fields.Many2many("uom.uom", compute="_compute_allowed_uom_ids")
    consignment_price_unit = fields.Monetary(string="Unit Price", required=True)
    consignment_discount = fields.Float(string="Discount %", default=0.0)
    commission_rate = fields.Float(string="Commission %", related='order_id.commission_rate', readonly=True)
    consignment_subtotal = fields.Monetary(string="Subtotal", compute="_compute_subtotal", store=True)

    @api.depends("product_uom_qty", "consignment_price_unit", "consignment_discount")
    def _compute_subtotal(self):
        for line in self:
            line.consignment_subtotal = line.product_uom_qty * line.consignment_price_unit * (1 - (line.consignment_discount or 0.0) / 100.0)

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
    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.name = self.product_id.display_name
        self.product_uom_id = self.product_id.uom_id
        self._onchange_price_inputs()

    @api.onchange("product_template_id")
    def _onchange_product_template_id(self):
        if not self.product_template_id:
            return
        if self.product_id.product_tmpl_id != self.product_template_id:
            self.product_id = self.product_template_id.product_variant_id

    @api.onchange("product_uom_qty", "product_uom_id", "product_id")
    def _onchange_price_inputs(self):
        self.consignment_price_unit = self.order_id._price_from_pricelist(
            self.order_id.pricelist_id,
            self.product_id,
            self.product_uom_qty,
            self.product_uom_id,
            self.order_id.date_order,
        )

    @api.constrains("product_uom_qty", "consignment_discount", "commission_rate")
    def _check_values(self):
        for line in self:
            line._check_positive_quantity()
            if not 0 <= line.consignment_discount <= 100:
                raise ValidationError(_("Discount must be between 0 and 100."))
            if line.commission_rate < 0:
                raise ValidationError(_("Commission cannot be negative."))

    def _check_positive_quantity(self):
        if self.product_uom_qty <= 0:
            raise ValidationError(_("Quantity must be greater than zero."))

    def _prepare_stock_move_vals(self):
        self.ensure_one()
        return {
            "description_picking": self.name or self.product_id.display_name,
            "product_id": self.product_id.id,
            "product_uom_qty": self.product_uom_qty,
            "product_uom": self.product_uom_id.id,
            "location_id": self.order_id.source_location_id.id,
            "location_dest_id": self.order_id.destination_location_id.id,
            "company_id": self.order_id.company_id.id,
            "origin": self.order_id.name,
            "tha_consignment_order_line_id": self.id,
        }
