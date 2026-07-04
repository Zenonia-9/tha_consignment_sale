from odoo import _, models
from odoo.exceptions import ValidationError


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

    def _next_consignment_sequence(self, code, sequence_xmlid, sequence_date=False, company=False):
        """Return the next sequence for a consignment document, per company.

        We keep the XMLID sequence as a template (company_id=False). For each company,
        we create (once) a company-specific copy and use that moving forward.
        """
        company = company or getattr(self, "company_id", False) or self.env.company
        Sequence = self.env["ir.sequence"].sudo().with_company(company)

        seq = Sequence.search([("code", "=", code), ("company_id", "=", company.id)], limit=1)
        if not seq:
            template = self.env.ref(sequence_xmlid, raise_if_not_found=False)
            if template:
                seq = template.copy({
                    "name": "%s (%s)" % (template.name, company.name),
                    "company_id": company.id,
                })

        return seq.next_by_id(sequence_date=sequence_date) if seq else False

    def _company_sequence_from_template(self, sequence_xmlid, company, code=False):
        """Return a company-safe sequence copied from the XMLID template when needed."""
        company = company or self.env.company
        Sequence = self.env["ir.sequence"].sudo().with_company(company)
        template = self.env.ref(sequence_xmlid, raise_if_not_found=False)
        if not template:
            return Sequence

        domain = [("company_id", "=", company.id)]
        if code:
            domain.append(("code", "=", code))
        else:
            domain.append(("name", "=", template.name))

        seq = Sequence.search(domain, limit=1)
        if not seq:
            copy_vals = {
                "name": "%s (%s)" % (template.name, company.name),
                "company_id": company.id,
            }
            if code:
                copy_vals["code"] = code
            seq = template.copy(copy_vals)
        return seq

    def _check_unique_consignment_name(self):
        for record in self:
            if not record.name or record.name in ("New", _("New")):
                continue
            domain = [
                ("id", "!=", record.id),
                ("name", "=", record.name),
                ("company_id", "=", record.company_id.id),
            ]
            if self.search_count(domain):
                raise ValidationError(_("Document number %s must be unique per company.") % record.name)

    def _consignment_picking_type(self, flow, name, code, sequence_code, sequence_xmlid, source_location, destination_location, company=False):
        company = company or self.env.company
        PickingType = self.env["stock.picking.type"].sudo().with_company(company)
        sequence = self._company_sequence_from_template(sequence_xmlid, company)
        supported_flows = {key for key, _label in PickingType._fields["tha_consignment_flow"].selection}
        flow_supported = flow in supported_flows
        domain = [
            ("company_id", "=", company.id),
            ("active", "=", True),
        ]
        if flow_supported:
            domain += [
                "|",
                ("tha_consignment_flow", "=", flow),
                "|",
                ("sequence_code", "=", sequence_code),
                ("name", "=", name),
            ]
        else:
            domain += [
                "|",
                ("sequence_code", "=", sequence_code),
                ("name", "=", name),
            ]
        picking_types = PickingType.search(domain)
        picking_type = picking_types.sorted(
            key=lambda current_type: (
                flow_supported and current_type.tha_consignment_flow == flow,
                current_type.sequence_code == sequence_code,
                bool(current_type.sequence_id),
                current_type.id,
            ),
            reverse=True,
        )[:1]
        if picking_type:
            vals = {}
            if flow_supported and picking_type.tha_consignment_flow != flow:
                vals["tha_consignment_flow"] = flow
            if picking_type.sequence_code != sequence_code:
                vals["sequence_code"] = sequence_code
            if picking_type.sequence_id.company_id != company or picking_type.sequence_id == self.env.ref(sequence_xmlid, raise_if_not_found=False):
                vals["sequence_id"] = sequence.id
            if vals:
                picking_type.write(vals)
            return picking_type
        create_vals = {
            "name": name,
            "code": code,
            "sequence_code": sequence_code,
            "sequence_id": sequence.id,
            "default_location_src_id": source_location.id,
            "default_location_dest_id": destination_location.id,
            "use_create_lots": False,
            "use_existing_lots": True,
            "company_id": company.id,
        }
        if flow_supported:
            create_vals["tha_consignment_flow"] = flow
        return PickingType.create(create_vals)

    def _price_from_pricelist(self, pricelist, product, quantity, uom=False, date=False):
        if not product:
            return 0.0
        if pricelist:
            return pricelist._get_product_price(product, quantity or 1.0, uom=uom or product.uom_id, date=date)
        return product.lst_price
