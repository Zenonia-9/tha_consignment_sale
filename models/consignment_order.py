from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ThaConsignmentOrder(models.Model):
    _name = "tha.consignment.order"
    _inherit = "tha.consignment.mixin"
    _description = "Consignment Order"
    _order = "create_date desc, id desc"

    name = fields.Char(default=lambda self: _("New"), copy=False, readonly=True, index=True)
    date_order = fields.Date(string="Order Date", default=fields.Date.context_today, required=True)
    commitment_date = fields.Date(
        string="Delivery Date",
        compute="_compute_commitment_date",
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        domain=[("is_consignment_shop", "=", True)],
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self._default_consignment_company(),
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        default=lambda self: self._default_salesperson(),
        required=True,
        check_company=True,
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
    )
    team_id = fields.Many2one(
        "crm.team",
        string="Sales Team",
        default=lambda self: self._default_sales_team(),
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    source_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Source Warehouse",
        default=lambda self: self._default_source_warehouse(),
        check_company=True,
        domain=[("tha_is_consignment_source_warehouse", "=", True)],
        required=True,
    )
    source_location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        default=lambda self: self._default_source_warehouse().lot_stock_id,
        required=True,
    )
    destination_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Destination Warehouse",
        default=lambda self: self._default_destination_warehouse(),
        check_company=True,
        domain=[("tha_is_consignment_warehouse", "=", True)],
        required=True,
    )
    destination_location_id = fields.Many2one(
        "stock.location",
        string="Destination Location",
        domain=[("usage", "=", "internal")],
        required=True,
    )
    pricelist_id = fields.Many2one("product.pricelist", string="Pricelist", default=lambda self: self._default_pricelist())
    currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_currency_id",
        store=True,
        readonly=False,
        required=True,
        default=lambda self: self._default_currency(),
    )
    commission_rate = fields.Float(string="Commission %", default=0.0)
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("cancel", "Cancelled")],
        default="draft",
        required=True,
        copy=False,
    )
    picking_id = fields.Many2one("stock.picking", string="Primary Delivery", copy=False, readonly=True)
    picking_state = fields.Selection(related="picking_id.state", string="Primary Delivery Status")
    picking_ids = fields.One2many("stock.picking", "tha_consignment_order_id", string="Delivery Records")
    transfer_count = fields.Integer(compute="_compute_transfer_summary", store=True, string="Deliveries")
    open_transfer_count = fields.Integer(compute="_compute_transfer_summary", store=True, string="Open Deliveries")
    transfer_state = fields.Selection(
        [
            ("no_transfer", "No Delivery"),
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
        string="Delivery Status",
    )
    settlement_ids = fields.One2many("tha.consignment.settlement", "order_id", string="Settlement Records")
    settlement_count = fields.Integer(compute="_compute_settlement_summary", string="Settlements")
    return_count = fields.Integer(compute="_compute_return_summary", string="Returns")
    can_settle = fields.Boolean(compute="_compute_can_settle")
    line_ids = fields.One2many("tha.consignment.order.line", "order_id", string="Order Lines", copy=True)
    amount_total = fields.Monetary(compute="_compute_amounts", store=True)
    commission_amount = fields.Monetary(compute="_compute_amounts", store=True)
    net_amount = fields.Monetary(compute="_compute_amounts", store=True)

    @api.depends("pricelist_id", "company_id")
    def _compute_currency_id(self):
        for order in self:
            order.currency_id = order.pricelist_id.currency_id or order.company_id.currency_id

    @api.depends("picking_ids.state", "picking_ids.date_done")
    def _compute_commitment_date(self):
        for order in self:
            done_deliveries = order.picking_ids.filtered(lambda picking: not picking.return_id and picking.state == "done")
            if done_deliveries:
                order.commitment_date = max(done_deliveries.mapped("date_done")).date()
            else:
                order.commitment_date = False

    @api.depends("line_ids.consignment_subtotal", "line_ids.display_type", "commission_rate")
    def _compute_amounts(self):
        for order in self:
            product_lines = order.line_ids.filtered(lambda line: not line.display_type)
            order.amount_total = sum(product_lines.mapped("consignment_subtotal"))
            order.commission_amount = sum(
                line.consignment_subtotal * (order.commission_rate or 0.0) / 100.0
                for line in product_lines
            )
            order.net_amount = order.amount_total - order.commission_amount

    @api.depends("picking_ids.state")
    def _compute_transfer_summary(self):
        active_states = ("draft", "waiting", "confirmed", "assigned")
        state_priority = {"assigned": 4, "confirmed": 3, "waiting": 2, "draft": 1}
        for order in self:
            deliveries = order.picking_ids.filtered(lambda picking: not picking.return_id)
            states = deliveries.mapped("state")
            order.transfer_count = len(deliveries)
            order.open_transfer_count = len(deliveries.filtered(lambda picking: picking.state in active_states))
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

    def _compute_settlement_summary(self):
        for order in self:
            order.settlement_count = len(order.settlement_ids.filtered(lambda settlement: settlement.state != "cancel"))

    def _compute_return_summary(self):
        for order in self:
            order.return_count = len(order._get_return_pickings())

    @api.depends("line_ids.remaining_qty", "state")
    def _compute_can_settle(self):
        for order in self:
            order.can_settle = (
                order.state == "confirmed"
                and any(
                    float_compare(
                        line.remaining_qty,
                        0.0,
                        precision_rounding=line.product_uom_id.rounding if line.product_uom_id else 0.01,
                    ) > 0
                    for line in order.line_ids.filtered(lambda line: not line.display_type)
                )
            )

    @api.constrains("name", "company_id")
    def _check_unique_name(self):
        self._check_unique_consignment_name()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
            partner = self.env["res.partner"].browse(vals.get("partner_id")) if vals.get("partner_id") else self.env["res.partner"]
            pricelist = (
                self.env["product.pricelist"].browse(vals["pricelist_id"])
                if vals.get("pricelist_id")
                else partner.consignment_pricelist_id or self._default_pricelist(company=company)
            )
            if pricelist and not vals.get("pricelist_id"):
                vals["pricelist_id"] = pricelist.id
            if not vals.get("currency_id"):
                vals["currency_id"] = (pricelist.currency_id or company.currency_id).id
        orders = super().create(vals_list)
        for order in orders:
            if not order.name or order.name in (_("New"), "New"):
                order._assign_sequence()
        return orders

    def _default_salesperson(self):
        return self.env.user

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

    def _default_sales_team(self, user=False, company=False):
        user = user or self.env.user
        team = self.env["crm.team"].with_context(default_team_id=False)._get_default_team_id(
            user_id=user.id,
        )
        if company:
            team = team.filtered(lambda current_team: not current_team.company_id or current_team.company_id == company)
        return team[:1]

    def _prepare_invoice_partner(self, partner):
        if not partner:
            return self.env["res.partner"]
        partner_id = partner.address_get(["invoice"]).get("invoice")
        return self.env["res.partner"].browse(partner_id)

    @api.onchange("company_id")
    def _onchange_company_id(self):
        source_wh = self._find_flagged_warehouse("tha_is_consignment_source_warehouse", self.company_id)
        dest_wh = self._find_flagged_warehouse("tha_is_consignment_warehouse", self.company_id)
        self.source_warehouse_id = source_wh
        self.source_location_id = source_wh.lot_stock_id
        self.destination_warehouse_id = dest_wh
        self.user_id = self._default_salesperson()
        self.team_id = self._default_sales_team(user=self.user_id, company=self.company_id)

    @api.onchange("user_id")
    def _onchange_user_id(self):
        self.team_id = self._default_sales_team(user=self.user_id, company=self.company_id)

    @api.onchange("source_warehouse_id")
    def _onchange_source_warehouse_id(self):
        self.source_location_id = self.source_warehouse_id.lot_stock_id

    @api.onchange("destination_warehouse_id")
    def _onchange_destination_warehouse_id(self):
        if self.destination_warehouse_id:
            self.destination_location_id = self.destination_warehouse_id.lot_stock_id

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.destination_location_id = self.partner_id.consignment_location_id
        self.pricelist_id = self.partner_id.consignment_pricelist_id or self.pricelist_id or self._default_pricelist(
            company=self.company_id,
            partner=self.partner_id,
        )
        self.currency_id = self.pricelist_id.currency_id or self.company_id.currency_id
        self.commission_rate = self.partner_id.commission_rate
        self.destination_warehouse_id = (
            self._warehouse_for_location(self.destination_location_id, self.company_id) or self.destination_warehouse_id
        )
        self.user_id = self.partner_id.user_id or self.partner_id.commercial_partner_id.user_id or self.user_id or self.env.user
        self.team_id = self._default_sales_team(user=self.user_id, company=self.company_id)
        for line in self.line_ids.filtered(lambda current_line: not current_line.display_type):
            line._onchange_price_inputs()

    @api.onchange("pricelist_id")
    def _onchange_pricelist_id(self):
        self.currency_id = self.pricelist_id.currency_id or self.company_id.currency_id

    def action_confirm(self):
        for order in self:
            if order.state != "draft":
                continue
            order._check_can_confirm()
            order._assign_sequence()
            picking = order._create_issue_picking()
            order.write({"picking_id": picking.id, "state": "confirmed"})
        return True

    def action_open_settle_wizard(self):
        self.ensure_one()
        if not self.can_settle:
            raise UserError(_("There is no remaining quantity to settle."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Settlement"),
            "res_model": "tha.consignment.settlement.create.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": self.id,
                "active_ids": self.ids,
                "active_model": "tha.consignment.order",
                "default_order_id": self.id,
            },
        }

    def _assign_sequence(self):
        if not self.name or self.name in (_("New"), "New"):
            self.name = self._next_consignment_sequence(
                "tha.consignment.order",
                "tha_consignment_sale.seq_consignment_order",
                self.date_order,
            ) or _("New")

    def action_cancel(self):
        for order in self:
            active_settlements = order.settlement_ids.filtered(lambda settlement: settlement.state != "cancel")
            if active_settlements:
                raise UserError(_("Cancel linked settlements before cancelling %s.") % order.display_name)
            done_pickings = order.picking_ids.filtered(lambda picking: picking.state == "done")
            if done_pickings:
                raise UserError(_("You cannot cancel %s because at least one delivery is done.") % order.display_name)
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
                raise UserError(_("You cannot delete %s while it is linked to an active delivery.") % order.display_name)
            active_settlements = order.settlement_ids.filtered(lambda settlement: settlement.state != "cancel")
            if active_settlements:
                raise UserError(_("You cannot delete %s while it is linked to active settlements.") % order.display_name)
        return super().unlink()

    def action_view_transfer(self):
        self.ensure_one()
        deliveries = self.picking_ids.filtered(lambda picking: not picking.return_id)
        if not deliveries:
            return {"type": "ir.actions.act_window_close"}
        if len(deliveries) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Delivery"),
                "res_model": "stock.picking",
                "view_mode": "form",
                "res_id": deliveries.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Deliveries"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", deliveries.ids)],
            "context": {"create": False},
        }

    def action_view_returns(self):
        self.ensure_one()
        return_pickings = self._get_return_pickings()
        if not return_pickings:
            return {"type": "ir.actions.act_window_close"}
        if len(return_pickings) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Return"),
                "res_model": "stock.picking",
                "view_mode": "form",
                "res_id": return_pickings.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Returns"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", return_pickings.ids)],
            "context": {"create": False},
        }

    def action_view_settlements(self):
        self.ensure_one()
        settlements = self.settlement_ids.filtered(lambda settlement: settlement.state != "cancel")
        if not settlements:
            return {"type": "ir.actions.act_window_close"}
        if len(settlements) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Settlement"),
                "res_model": "tha.consignment.settlement",
                "view_mode": "form",
                "res_id": settlements.id,
                "context": {"create": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Settlements"),
            "res_model": "tha.consignment.settlement",
            "view_mode": "list,form",
            "domain": [("id", "in", settlements.ids)],
            "context": {"create": False},
        }

    def _get_return_pickings(self):
        self.ensure_one()
        return self.env["stock.picking"].search([
            ("tha_consignment_order_id", "=", self.id),
            ("return_id", "!=", False),
        ])

    def _validate_print_selection(self):
        orders = self.exists()
        if not orders:
            raise UserError(_("No consignment orders selected."))
        if any(order.state != "confirmed" for order in orders):
            raise UserError(_("Only confirmed consignment orders can be printed."))
        if any(not order.line_ids.filtered(lambda line: not line.display_type) for order in orders):
            raise UserError(_("Each selected consignment order must have at least one product line."))
        company = orders[0].company_id
        if any(order.company_id != company for order in orders):
            raise UserError(_("Selected consignment orders must belong to the same company."))
        if any(not order.currency_id for order in orders):
            raise UserError(_("Each selected consignment order must have a currency."))
        if any(
            line.product_uom_qty <= 0
            for order in orders
            for line in order.line_ids.filtered(lambda current_line: not current_line.display_type)
        ):
            raise UserError(_("Product quantities must be greater than zero before printing."))
        if any(
            line.consignment_price_unit < 0
            for order in orders
            for line in order.line_ids.filtered(lambda current_line: not current_line.display_type)
        ):
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
        product_lines = self.line_ids.filtered(lambda line: not line.display_type)
        if not product_lines:
            raise UserError(_("Add at least one product line."))
        if not self.source_location_id or not self.destination_location_id:
            raise UserError(_("Source and destination locations are required."))
        if self.source_location_id == self.destination_location_id:
            raise UserError(_("Source and destination locations must be different."))
        if self.destination_location_id.usage != "internal":
            raise UserError(_("Consignment destination must be an internal location."))
        for line in product_lines:
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
        move_commands = [
            Command.create(line._prepare_stock_move_vals())
            for line in self.line_ids.filtered(lambda order_line: not order_line.display_type)
        ]
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

    order_id = fields.Many2one("tha.consignment.order", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id", store=True)
    display_type = fields.Selection(
        selection=[
            ("line_section", "Section"),
            ("line_note", "Note"),
        ],
        default=False,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain=[("type", "=", "consu")],
    )
    name = fields.Text(string="Description", required=True)
    product_uom_qty = fields.Float(string="Quantity", default=1.0, digits="Product Unit")
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        domain='[("id", "in", allowed_uom_ids)]',
    )
    allowed_uom_ids = fields.Many2many("uom.uom", compute="_compute_allowed_uom_ids")
    consignment_price_unit = fields.Monetary(string="Unit Price")
    consignment_discount = fields.Float(string="Disc.%", default=0.0)
    commission_rate = fields.Float(string="Commission %", related="order_id.commission_rate", readonly=True)
    consignment_subtotal = fields.Monetary(string="Subtotal", compute="_compute_subtotal", store=True)
    qty_delivered = fields.Float(string="Delivered", compute="_compute_progress_quantities", digits="Product Unit")
    qty_invoiced = fields.Float(string="Invoiced", compute="_compute_progress_quantities", digits="Product Unit")
    qty_returned = fields.Float(string="Returned", compute="_compute_progress_quantities", digits="Product Unit")
    qty_settled = fields.Float(string="Settled", compute="_compute_progress_quantities", digits="Product Unit")
    remaining_qty = fields.Float(string="Remaining", compute="_compute_progress_quantities", digits="Product Unit")

    @api.depends("product_uom_qty", "consignment_price_unit", "consignment_discount", "display_type")
    def _compute_subtotal(self):
        for line in self:
            if line.display_type:
                line.consignment_subtotal = 0.0
            else:
                line.consignment_subtotal = line.product_uom_qty * line.consignment_price_unit * (
                    1 - (line.consignment_discount or 0.0) / 100.0
                )

    @api.depends("product_id", "product_id.uom_id", "product_id.uom_ids")
    def _compute_allowed_uom_ids(self):
        for line in self:
            line.allowed_uom_ids = line.product_id.uom_id | line.product_id.uom_ids

    def _compute_progress_quantities(self):
        StockMove = self.env["stock.move"].sudo()
        SettlementLine = self.env["tha.consignment.settlement.line"].sudo()
        for line in self:
            if line.display_type or not line.product_id:
                line.qty_delivered = 0.0
                line.qty_invoiced = 0.0
                line.qty_returned = 0.0
                line.qty_settled = 0.0
                line.remaining_qty = 0.0
                continue

            delivered_moves = StockMove.search([
                ("tha_consignment_order_line_id", "=", line.id),
                ("state", "=", "done"),
                ("picking_id.return_id", "=", False),
            ])
            returned_moves = StockMove.search([
                ("origin_returned_move_id.tha_consignment_order_line_id", "=", line.id),
                ("picking_id.tha_consignment_order_id", "=", line.order_id.id),
                ("picking_id.return_id", "!=", False),
                ("state", "=", "done"),
            ])
            settlement_lines = SettlementLine.search([
                ("order_line_id", "=", line.id),
                ("settlement_id.state", "!=", "cancel"),
            ])
            invoiced_lines = settlement_lines.filtered(
                lambda settlement_line: settlement_line.settlement_id.invoice_id
                and settlement_line.settlement_id.invoice_id.state != "cancel"
            )

            line.qty_delivered = sum(line._convert_move_qty(move, move.quantity) for move in delivered_moves)
            line.qty_returned = sum(line._convert_move_qty(move, move.quantity) for move in returned_moves)
            line.qty_settled = sum(
                settlement_line.product_uom_id._compute_quantity(
                    settlement_line.product_uom_qty,
                    line.product_uom_id,
                )
                for settlement_line in settlement_lines
            )
            line.qty_invoiced = sum(
                settlement_line.product_uom_id._compute_quantity(
                    settlement_line.product_uom_qty,
                    line.product_uom_id,
                )
                for settlement_line in invoiced_lines
            )
            line.remaining_qty = max(line.product_uom_qty - line.qty_returned - line.qty_settled, 0.0)

    def _convert_move_qty(self, move, quantity):
        self.ensure_one()
        return move.product_uom._compute_quantity(quantity, self.product_uom_id or self.product_id.uom_id)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.display_type:
            return
        self.name = self.product_id.display_name
        self.product_uom_id = self.product_id.uom_id
        self._onchange_price_inputs()

    @api.onchange("product_uom_qty", "product_uom_id", "product_id")
    def _onchange_price_inputs(self):
        if self.display_type or not self.product_id:
            return
        self.consignment_price_unit = self.order_id._price_from_pricelist(
            self.order_id.pricelist_id,
            self.product_id,
            self.product_uom_qty,
            self.product_uom_id,
            self.order_id.date_order,
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("display_type"):
                vals.update({
                    "product_id": False,
                    "product_uom_id": False,
                    "product_uom_qty": 0.0,
                    "consignment_price_unit": 0.0,
                    "consignment_discount": 0.0,
                })
        return super().create(vals_list)

    def write(self, vals):
        if "display_type" in vals and self.filtered(lambda line: line.display_type != vals.get("display_type")):
            raise UserError(_("You cannot change the type of an order line. Delete it and create a new one instead."))
        return super().write(vals)

    @api.constrains("display_type", "product_id", "product_uom_id", "product_uom_qty", "consignment_discount", "commission_rate")
    def _check_values(self):
        for line in self:
            if line.display_type:
                if line.product_id or line.product_uom_id:
                    raise ValidationError(_("Section and note lines cannot have a product or unit."))
                continue
            if not line.product_id or not line.product_uom_id:
                raise ValidationError(_("Product and unit are required on product lines."))
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
