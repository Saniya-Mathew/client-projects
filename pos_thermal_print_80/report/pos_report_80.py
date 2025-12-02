# -*- coding: utf-8 -*-
from odoo import api, models


class ReportFiscalPos80(models.AbstractModel):
    _name = 'report.pos_thermal_print_80.report_pos_order_80'
    _description = 'POS 80mm Thermal Report with fiscalization data'

    def aggregate_taxes(self, orders, lines):
        """
        Aggregates tax base and VAT amounts for a given set of order lines,
        while also considering the associated orders.
        Fixed tax calculation to use actual tax amounts instead of calculated percentages.
        """
        aggregated_taxes = {}
        for line in lines:
            order = line.order_id
            if not line.tax_ids_after_fiscal_position:  # Check if there are no taxes
                continue
            for tax in line.tax_ids_after_fiscal_position:
                tax_key = (tax.id, order.id)
                # Calculate actual tax amount from line totals
                actual_tax_amount = line.price_subtotal_incl - line.price_subtotal
                
                # If multiple taxes on one line, distribute proportionally
                total_tax_percent = sum(t.l10n_hr_fiscal_percent for t in line.tax_ids_after_fiscal_position)
                if total_tax_percent > 0:
                    tax_proportion = tax.l10n_hr_fiscal_percent / total_tax_percent
                    proportional_tax_amount = actual_tax_amount * tax_proportion
                else:
                    proportional_tax_amount = 0
                
                if tax_key in aggregated_taxes:
                    aggregated_taxes[tax_key]['base'] += line.price_subtotal
                    aggregated_taxes[tax_key]['vat'] += order.currency_id.round(proportional_tax_amount)
                else:
                    aggregated_taxes[tax_key] = {
                        'order_name': order.name,
                        'label': tax.invoice_label,
                        'percent': tax.l10n_hr_fiscal_percent,
                        'base': line.price_subtotal,
                        'vat': order.currency_id.round(proportional_tax_amount)
                    }
        return aggregated_taxes

    @api.model
    def _get_report_values(self, docids, data=None):
        orders = self.env['pos.order'].browse(docids)

        # Aggregate taxes for each order individually and include in the docs
        docs = []
        for order in orders:
            aggregated_tax = self.aggregate_taxes(order, order.mapped('lines'))
            docs.append({
                'order': order,
                'aggregated_taxes': aggregated_tax
            })

        return {
            'doc_ids': docids,
            'doc_model': 'pos.order',
            'docs': docs,
        }
