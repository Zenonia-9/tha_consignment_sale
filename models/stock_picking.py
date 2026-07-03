from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    tha_is_consignment_transfer = fields.Boolean(string="Consignment Transfer", copy=False, index=True)
    tha_consignment_order_id = fields.Many2one("tha.consignment.order", string="Consignment Order", copy=False)
    tha_consignment_settlement_id = fields.Many2one("tha.consignment.settlement", string="Consignment Settlement", copy=False)

    def _create_backorder_picking(self):
        backorder = super()._create_backorder_picking()
        consignment_vals = {
            "tha_is_consignment_transfer": self.tha_is_consignment_transfer,
            "tha_consignment_order_id": self.tha_consignment_order_id.id,
            "tha_consignment_settlement_id": self.tha_consignment_settlement_id.id,
        }
        if any(consignment_vals.values()):
            backorder.write(consignment_vals)
        return backorder


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    tha_consignment_flow = fields.Selection(
        [
            ("issue", "Consignment Issue"),
            ("sold", "Consignment Sold"),
        ],
        string="Consignment Flow",
        copy=False,
        index=True,
    )


class StockMove(models.Model):
    _inherit = "stock.move"

    tha_consignment_order_line_id = fields.Many2one("tha.consignment.order.line", string="Consignment Order Line", copy=False)
    tha_consignment_settlement_line_id = fields.Many2one("tha.consignment.settlement.line", string="Consignment Settlement Line", copy=False)
