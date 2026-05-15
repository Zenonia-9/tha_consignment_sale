from odoo import models


class ThaConsignmentMixin(models.AbstractModel):
    _name = "tha.consignment.mixin"
    _description = "Consignment Helper Mixin"

    def _default_consignment_company(self):
        return self.env.company

    def _find_flagged_warehouse(self, flag_field, company=False):
        company = company or self.env.company
        return self.env["stock.warehouse"].search([
            ("company_id", "=", company.id),
            (flag_field, "=", True),
        ], limit=1)

    def _default_source_warehouse(self):
        return self._find_flagged_warehouse("tha_is_consignment_source_warehouse", self._default_consignment_company())

    def _default_destination_warehouse(self):
        return self._find_flagged_warehouse("tha_is_consignment_warehouse", self._default_consignment_company())

    def _warehouse_for_location(self, location, company=False):
        if not location:
            return self.env["stock.warehouse"]
        parent_ids = [int(item) for item in (location.parent_path or "").split("/") if item]
        warehouses = self.env["stock.warehouse"].search([("company_id", "=", (company or location.company_id or self.env.company).id)])
        return warehouses.filtered(lambda wh: wh.lot_stock_id.id in parent_ids or wh.view_location_id.id in parent_ids)[:1]

    def _customer_location(self):
        return self.env.ref("stock.stock_location_customers")

    def _consignment_picking_type(self, flow, name, code, sequence_code, sequence_xmlid, source_location, destination_location, company=False):
        company = company or self.env.company
        PickingType = self.env["stock.picking.type"].sudo().with_company(company)
        picking_type = PickingType.search([
            ("company_id", "=", company.id),
            ("tha_consignment_flow", "=", flow),
            ("active", "=", True),
        ], limit=1)
        if picking_type:
            return picking_type
        return PickingType.create({
            "name": name,
            "code": code,
            "sequence_code": sequence_code,
            "sequence_id": self.env.ref(sequence_xmlid).id,
            "default_location_src_id": source_location.id,
            "default_location_dest_id": destination_location.id,
            "use_create_lots": False,
            "use_existing_lots": True,
            "company_id": company.id,
            "tha_consignment_flow": flow,
        })

    def _price_from_pricelist(self, pricelist, product, quantity, uom=False, date=False):
        if not product:
            return 0.0
        if pricelist:
            return pricelist._get_product_price(product, quantity or 1.0, uom=uom or product.uom_id, date=date)
        return product.lst_price
