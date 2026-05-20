from odoo import _, api, models
from odoo.exceptions import UserError


def _get_consignment_order_report_values(report_model, docids, data=None):
    data = data or {}
    if not docids and data.get("active_ids"):
        docids = data.get("active_ids")

    docs = report_model.env["tha.consignment.order"].browse(docids).exists()
    if not docs:
        raise UserError(_("Please select at least one consignment order to print."))
    if any(order.state == "cancel" for order in docs):
        raise UserError(_("Cancelled consignment orders cannot be printed."))
    if any(not order.line_ids for order in docs):
        raise UserError(_("Each selected consignment order must have at least one product line."))

    partner = docs[:1].partner_id
    if not partner or any(order.partner_id != partner for order in docs):
        raise UserError(_("Selected consignment orders must have the same shop."))

    company = docs[:1].company_id
    if any(order.company_id != company for order in docs):
        raise UserError(_("Selected consignment orders must belong to the same company."))

    return {
        "doc_ids": docs.ids,
        "doc_model": "tha.consignment.order",
        "docs": docs,
        "data": data,
    }


class ConsignmentOrderReport(models.AbstractModel):
    _name = "report.tha_consignment_sale.report_consignment_order_document"
    _description = "Consignment Order Report"
    _table = "tcs_report_consignment_order_a4"
    _auto = False

    @api.model
    def _get_report_values(self, docids, data=None):
        return _get_consignment_order_report_values(self, docids, data=data)


class ConsignmentOrderA5Report(models.AbstractModel):
    _name = "report.tha_consignment_sale.report_consignment_order_document_a5"
    _description = "Consignment Order Report A5"
    _table = "tcs_report_consignment_order_a5"
    _auto = False

    @api.model
    def _get_report_values(self, docids, data=None):
        return _get_consignment_order_report_values(self, docids, data=data)
