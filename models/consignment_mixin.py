from odoo import models


class ThaConsignmentMixin(models.AbstractModel):
    _name = "tha.consignment.mixin"
    _description = "Consignment Helper Mixin"

    def _default_consignment_company(self):
        warehouse = self.env["stock.warehouse"].search([("code", "=", "YGN")], limit=1)
        return warehouse.company_id or self.env.company

    def _find_warehouse(self, code=False, name=False, company=False):
        Warehouse = self.env["stock.warehouse"]
        domain = [("company_id", "=", (company or self.env.company).id)]
        warehouse = Warehouse
        if code:
            warehouse = Warehouse.search(domain + [("code", "=", code)], limit=1)
        if not warehouse and name:
            warehouse = Warehouse.search(domain + [("name", "ilike", name)], limit=1)
        if not warehouse and code:
            warehouse = Warehouse.search([("code", "=", code)], limit=1)
        if not warehouse and name:
            warehouse = Warehouse.search([("name", "ilike", name)], limit=1)
        return warehouse

    def _default_source_warehouse(self):
        company = self._default_consignment_company()
        return self._find_warehouse("YGN", "YGN Warehouse", company)

    def _default_destination_warehouse(self):
        company = self._default_consignment_company()
        return self._find_warehouse("CSWH", "Consignment Warehouse", company)

    def _warehouse_for_location(self, location, company=False):
        if not location:
            return self.env["stock.warehouse"]
        parent_ids = [int(item) for item in (location.parent_path or "").split("/") if item]
        warehouses = self.env["stock.warehouse"].search([("company_id", "=", (company or location.company_id or self.env.company).id)])
        return warehouses.filtered(lambda wh: wh.lot_stock_id.id in parent_ids or wh.view_location_id.id in parent_ids)[:1]

    def _customer_location(self):
        return self.env.ref("stock.stock_location_customers")

    def _price_from_pricelist(self, pricelist, product, quantity, uom=False, date=False):
        if not product:
            return 0.0
        if pricelist:
            return pricelist._get_product_price(product, quantity or 1.0, uom=uom or product.uom_id, date=date)
        return product.lst_price
