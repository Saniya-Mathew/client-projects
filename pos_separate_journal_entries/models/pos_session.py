# -*- coding: utf-8 -*-
from odoo import fields,models, api
from collections import defaultdict
from odoo.tools import float_is_zero
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError
from odoo.tools import float_compare
import math



class PosSession(models.Model):
    _inherit = 'pos.session'

    def _accumulate_amounts(self, data):
        amounts = lambda: {'amount': 0.0, 'amount_converted': 0.0}
        tax_amounts = lambda: {
            'amount': 0.0,
            'amount_converted': 0.0,
            'base_amount': 0.0,
            'base_amount_converted': 0.0
        }

        split_receivables_bank = defaultdict(amounts)
        split_receivables_cash = defaultdict(amounts)
        split_receivables_pay_later = defaultdict(amounts)
        combine_receivables_bank = defaultdict(amounts)
        combine_receivables_cash = defaultdict(amounts)
        combine_receivables_pay_later = defaultdict(amounts)
        combine_invoice_receivables = defaultdict(amounts)
        split_invoice_receivables = defaultdict(amounts)
        sales = defaultdict(amounts)
        taxes = defaultdict(tax_amounts)
        stock_expense = defaultdict(amounts)
        stock_return = defaultdict(amounts)
        stock_output = defaultdict(amounts)
        rounding_difference = {'amount': 0.0, 'amount_converted': 0.0}
        combine_inv_payment_receivable_lines = defaultdict(lambda: self.env['account.move.line'])
        split_inv_payment_receivable_lines = defaultdict(lambda: self.env['account.move.line'])

        rounded_globally = self.company_id.tax_calculation_rounding_method == 'round_globally'
        pos_receivable_account = self.company_id.account_default_pos_receivable_account_id
        currency_rounding = self.currency_id.rounding
        closed_orders = self._get_closed_orders()

        for order in closed_orders:
            order_is_invoiced = order.is_invoiced

            for payment in order.payment_ids:
                amount = payment.amount
                if float_is_zero(amount, precision_rounding=currency_rounding):
                    continue

                payment_method = payment.payment_method_id
                payment_type = payment_method.type
                date = payment.payment_date

                if payment_type != 'pay_later':
                    if payment_type == 'cash':
                        split_receivables_cash[payment] = self._update_amounts(
                            split_receivables_cash[payment], {'amount': amount}, date
                        )
                    elif payment_type == 'bank':
                        split_receivables_bank[payment] = self._update_amounts(
                            split_receivables_bank[payment], {'amount': amount}, date
                        )

                    if order_is_invoiced:
                        split_inv_payment_receivable_lines[payment] |= payment.account_move_id.line_ids.filtered(
                            lambda line: line.account_id == pos_receivable_account
                        )
                        split_invoice_receivables[payment] = self._update_amounts(
                            split_invoice_receivables[payment], {'amount': amount}, order.date_order
                        )

                if payment_type == 'pay_later' and not order_is_invoiced:
                    split_receivables_pay_later[payment] = self._update_amounts(
                        split_receivables_pay_later[payment], {'amount': amount}, date
                    )

            if not order_is_invoiced:
                order_taxes = defaultdict(tax_amounts)

                for order_line in order.lines:
                    line = self._prepare_line(order_line)
                    line_amount_positive = abs(line['amount'])

                    sale_key = (
                        order.id,
                        line['income_account_id'],
                        -1 if line['amount'] < 0 else 1,
                        tuple((tax['id'], tax['account_id'], tax['tax_repartition_line_id']) for tax in line['taxes']),
                        line['base_tags'],
                    )

                    sales[sale_key] = self._update_amounts(
                        sales[sale_key], {'amount': line_amount_positive}, line['date_order'], round=False
                    )
                    sales[sale_key].setdefault('tax_amount', 0.0)

                    for tax in line['taxes']:
                        tax_amt = abs(tax['amount'])
                        base_amt = abs(tax.get('base', 0.0))

                        tax_key = (
                            order.id,
                            tax['account_id'] or line['income_account_id'],
                            tax['tax_repartition_line_id'],
                            tax['id'],
                            tuple(tax['tag_ids'])
                        )

                        sales[sale_key]['tax_amount'] += tax_amt

                        order_taxes[tax_key] = self._update_amounts(
                            order_taxes[tax_key],
                            {'amount': tax_amt, 'base_amount': base_amt},
                            tax.get('date_order', line['date_order']),
                            round=not rounded_globally
                        )

                for tax_key, amounts_tax in order_taxes.items():
                    if rounded_globally:
                        amounts_tax = self._round_amounts(amounts_tax)
                    for amount_key, amount in amounts_tax.items():
                        taxes[tax_key][amount_key] += amount

                if self.config_id.cash_rounding:
                    diff = order.amount_paid - order.amount_total
                    rounding_difference = self._update_amounts(
                        rounding_difference, {'amount': diff}, order.date_order
                    )

                partners = (order.partner_id | order.partner_id.commercial_partner_id)
                partners._increase_rank('customer_rank')

        MoveLine = self.env['account.move.line'].with_context(
            check_move_validity=False, skip_invoice_sync=True
        )
        split_receivables_online = defaultdict(amounts)

        data.update({
            'taxes': taxes,
            'sales': sales,
            'stock_expense': stock_expense,
            'split_receivables_bank': split_receivables_bank,
            'combine_receivables_bank': combine_receivables_bank,
            'split_receivables_cash': split_receivables_cash,
            'combine_receivables_cash': combine_receivables_cash,
            'split_receivables_online': split_receivables_online,
            'combine_receivables_pay_later': combine_receivables_pay_later,
            'split_receivables_pay_later': split_receivables_pay_later,
            'combine_invoice_receivables': combine_invoice_receivables,
            'split_invoice_receivables': split_invoice_receivables,
            'combine_inv_payment_receivable_lines': combine_inv_payment_receivable_lines,
            'split_inv_payment_receivable_lines': split_inv_payment_receivable_lines,
            'stock_return': stock_return,
            'stock_output': stock_output,
            'rounding_difference': rounding_difference,
            'MoveLine': MoveLine,
        })
        return data

    @api.model
    def _get_tax_vals(self, key, amount, amount_converted, base_amount_converted):
        order_id, account_id, repartition_line_id, tax_id, tag_ids = key
        order = self.env['pos.order'].browse(order_id)
        tax = self.env['account.tax'].browse(tax_id)
        partial_args = {
            'name': tax.name,
            'account_id': account_id,
            'move_id': self.move_id.id,
            'tax_base_amount': abs(base_amount_converted),
            'tax_repartition_line_id': repartition_line_id,
            'tax_tag_ids': [(6, 0, tag_ids)],
            'display_type': 'tax',
            'pos_order_id': order_id,
            'partner_id': order.partner_id.id if order.partner_id else False,
        }
        return self._credit_amounts(partial_args, amount, amount_converted)

    @api.model
    def _get_sale_vals(self, key, amount, amount_converted):
        order_id, account_id, sign, tax_keys, base_tag_ids = key
        order = self.env['pos.order'].browse(order_id)
        account = self.env['account.account'].browse(account_id)
        partial_args = {
            'name': account.name,
            'account_id': account_id,
            'move_id': self.move_id.id,
            'tax_ids': [(6, 0, [tax[0] for tax in tax_keys])] if tax_keys else False,
            'tax_tag_ids': [(6, 0, base_tag_ids)] if base_tag_ids else False,
            'display_type': 'product',
            'pos_order_id': order_id,
            'partner_id': order.partner_id.id if order.partner_id else False,
        }
        return self._credit_amounts(partial_args, amount, amount_converted)

    def action_backfill_order_partners(self):
        # Find ALL orders without a customer (from all sessions)
        orders = self.env['pos.order'].search([
            ('partner_id', '=', False)
        ])

        for order in orders:
            order.partner_id = 69

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Global Backfill Completed",
                'message': f"{len(orders)} orders updated with Partner 69.",
                'sticky': False,
            }
        }

    def action_fix_partner_2250(self):
        """Safely assign partner to account 2250 lines """
        for session in self:
            move = session.move_id
            if not move:
                continue
            print(f"\n=== Fix 2250 partners for session {session.name} (move {move.id}) ===")
            orders = self.env['pos.order'].search([('session_id', '=', session.id)])
            print(f"Found {len(orders)} order(s) in session.")

            lines_2250 = move.line_ids.filtered(lambda l: l.account_id.code == '2250')
            print(f"Found {len(lines_2250)} move line(s) for account 2250.")

            def order_amount_candidates(order):
                untaxed = float(sum(order.lines.mapped('price_subtotal')) or 0.0)
                net = float(order.amount_total - order.amount_tax or 0.0)
                total = float(order.amount_total or 0.0)
                return [round(untaxed, 2), round(abs(untaxed), 2),
                        round(net, 2), round(abs(net), 2), round(total, 2)]

            for line in lines_2250:
                line_amount = float(line.credit or line.debit)
                print(f"Attempting to match line {line.id} amount={line_amount}")

                matched_order = None
                for order in orders:
                    for cand in order_amount_candidates(order):
                        if math.isclose(line_amount, cand, abs_tol=0.02):  # 2 cents tolerance
                            matched_order = order
                            break
                    if matched_order:
                        break

                partner_to_set = False
                if matched_order:
                    partner_to_set = matched_order.partner_id or False
                    print(
                        f"  → matched order {matched_order.name}, partner: {partner_to_set.name if partner_to_set else 'None'}")
                else:
                    partners = orders.mapped('partner_id').filtered(lambda p: p)
                    if partners:
                        partner_to_set = partners[0]
                        print(f"  → no exact match, using first session partner {partner_to_set.name}")
                    else:
                        print("  → no partner to assign")

                try:
                    line.with_context(check_move_validity=False).write({
                        'partner_id': partner_to_set.id if partner_to_set else False
                    })
                except Exception as e:
                    print(f"  ! Failed writing partner on line {line.id}: {e}")

            print("\nRounding all move line amounts to 2 decimals...")
            for l in move.line_ids:
                new_debit = round(float(l.debit or 0.0), 2)
                new_credit = round(float(l.credit or 0.0), 2)
                if new_debit != float(l.debit) or new_credit != float(l.credit):
                    try:
                        l.with_context(check_move_validity=False).write({
                            'debit': new_debit,
                            'credit': new_credit,
                        })
                        print(
                            f"  - corrected line {l.id}: debit {l.debit} -> {new_debit}, credit {l.credit} -> {new_credit}")
                    except Exception as e:
                        print(f"  ! Failed to rewrite amounts for line {l.id}: {e}")

            print("\nRecomputing move amounts to ensure balance...")
            move._compute_amount()

            total_debit = sum(float(l.debit or 0.0) for l in move.line_ids)
            total_credit = sum(float(l.credit or 0.0) for l in move.line_ids)
            diff = round(total_debit - total_credit, 2)

            if float_compare(diff, 0.0, precision_digits=2) != 0:
                msg = (
                    f"After assigning partners and rounding, move {move.id} is still unbalanced: "
                    f"Debits={total_debit:.2f}, Credits={total_credit:.2f}, Diff={diff:.2f}."
                )
                print("ERROR:", msg)
                raise UserError(msg)
            print("Move is balanced and partners assigned successfully.")
        return True
