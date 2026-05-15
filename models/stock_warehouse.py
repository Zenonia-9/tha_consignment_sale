from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    tha_is_consignment_source_warehouse = fields.Boolean(string="Is Consignment Source Warehouse")
    tha_is_consignment_warehouse = fields.Boolean(string="Is Consignment Warehouse")
