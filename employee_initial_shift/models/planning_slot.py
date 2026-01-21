from odoo import fields, models


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    employee_initial_shift = fields.Selection(
        related='employee_id.initial_shift',
        string='Initial Shift',
        store=True,
    )

