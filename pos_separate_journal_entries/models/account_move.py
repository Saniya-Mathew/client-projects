from odoo import fields, models

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    pos_order_id = fields.Many2one(
        comodel_name='pos.order',
        string='POS Order',
        ondelete='restrict',
        index=True,
        readonly=True,
        help="The Point of Sale Order that generated this accounting entry line."
    )
