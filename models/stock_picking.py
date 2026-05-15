from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    tha_is_consignment_transfer = fields.Boolean(string="Consignment Transfer", copy=False, index=True)
    tha_consignment_order_id = fields.Many2one("tha.consignment.order", string="Consignment Order", copy=False)
    tha_consignment_settlement_id = fields.Many2one("tha.consignment.settlement", string="Consignment Settlement", copy=False)
    tha_consignment_return_id = fields.Many2one("tha.consignment.return", string="Consignment Return", copy=False)


class StockMove(models.Model):
    _inherit = "stock.move"

    tha_consignment_order_line_id = fields.Many2one("tha.consignment.order.line", string="Consignment Order Line", copy=False)
    tha_consignment_settlement_line_id = fields.Many2one("tha.consignment.settlement.line", string="Consignment Settlement Line", copy=False)
    tha_consignment_return_line_id = fields.Many2one("tha.consignment.return.line", string="Consignment Return Line", copy=False)
