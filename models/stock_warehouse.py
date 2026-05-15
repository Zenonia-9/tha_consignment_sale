from odoo import api, fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    tha_is_consignment_source_warehouse = fields.Boolean(string="Is Consignment Source Warehouse")
    tha_is_consignment_warehouse = fields.Boolean(string="Is Consignment Warehouse")


class StockLocation(models.Model):
    _inherit = "stock.location"

    tha_is_consignment_location = fields.Boolean(
        string="Consignment Location",
        compute="_compute_tha_is_consignment_location",
        search="_search_tha_is_consignment_location",
    )

    @api.depends("parent_path")
    def _compute_tha_is_consignment_location(self):
        consignment_locations = self._tha_consignment_location_domain_ids()
        for location in self:
            location.tha_is_consignment_location = location.id in consignment_locations

    def _search_tha_is_consignment_location(self, operator, value):
        ids = self._tha_consignment_location_domain_ids()
        positive = operator in ("=", "==") and value or operator in ("!=", "<>") and not value
        return [("id", "in" if positive else "not in", list(ids))]

    def _tha_consignment_location_domain_ids(self):
        warehouses = self.env["stock.warehouse"].search([("tha_is_consignment_warehouse", "=", True)])
        root_ids = (warehouses.mapped("lot_stock_id") | warehouses.mapped("view_location_id")).ids
        if not root_ids:
            return set()
        return set(self.env["stock.location"].search([("id", "child_of", root_ids)]).ids)
