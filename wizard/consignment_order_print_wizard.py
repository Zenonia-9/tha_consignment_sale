from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ThaConsignmentOrderPrintWizard(models.TransientModel):
    _name = "tha.consignment.order.print.wizard"
    _description = "Consignment Order Print Wizard"

    shop_name = fields.Char(string="Shop", readonly=True)
    order_count = fields.Integer(string="Selected Orders", readonly=True)
    paper_size = fields.Selection(
        selection=[
            ("a4", "A4"),
            ("a5", "A5"),
        ],
        string="Paper Size",
        required=True,
        default="a4",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") != "tha.consignment.order":
            raise UserError(_("This wizard must be opened from Consignment Orders."))

        orders = self.env["tha.consignment.order"].browse(self.env.context.get("active_ids", []))
        orders = orders._validate_print_selection()
        res.update(
            {
                "shop_name": orders[0].partner_id.display_name,
                "order_count": len(orders),
                "paper_size": "a5" if len(orders) <= 2 else "a4",
            }
        )
        return res

    def action_print(self):
        self.ensure_one()
        orders = self.env["tha.consignment.order"].browse(self.env.context.get("active_ids", []))
        orders = orders._validate_print_selection()
        report_ref = (
            "tha_consignment_sale.action_report_consignment_order_a5"
            if self.paper_size == "a5"
            else "tha_consignment_sale.action_report_consignment_order_a4"
        )
        return self.env.ref(report_ref).report_action(
            orders,
            data={"active_ids": orders.ids, "paper_size": self.paper_size},
        )
