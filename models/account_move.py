from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    tha_consignment_settlement_id = fields.Many2one(
        "tha.consignment.settlement",
        string="Consignment Settlement",
        readonly=True,
        copy=False,
        index=True,
    )

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
