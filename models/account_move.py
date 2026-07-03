from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    tha_consignment_settlement_id = fields.Many2one(
        "tha.consignment.settlement",
        string="Consignment Settlement",
        compute="_compute_tha_consignment_settlement_id",
    )

    def _compute_tha_consignment_settlement_id(self):
        settlement_by_invoice = {}
        settlements = self.env["tha.consignment.settlement"].sudo().search([
            "|",
            ("invoice_id", "in", self.ids),
            ("commission_bill_id", "in", self.ids),
        ])
        for settlement in settlements:
            if settlement.invoice_id:
                settlement_by_invoice[settlement.invoice_id.id] = settlement
            if settlement.commission_bill_id:
                settlement_by_invoice[settlement.commission_bill_id.id] = settlement
        for move in self:
            move.tha_consignment_settlement_id = settlement_by_invoice.get(move.id)

    def action_view_consignment_settlement(self):
        self.ensure_one()
        settlement = self.tha_consignment_settlement_id
        if not settlement:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "name": _("Consignment Settlement"),
            "res_model": "tha.consignment.settlement",
            "view_mode": "form",
            "res_id": settlement.id,
            "context": {"create": False},
        }
