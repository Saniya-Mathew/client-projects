from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlanningSlotTemplate(models.Model):
    _inherit = 'planning.slot.template'

    skill_ids = fields.Many2many(
        'planning.skill',
        'planning_template_skill_rel',
        'template_id',
        'skill_id',
        string='Skills',required=True,
    )

    initial_shift = fields.Selection(
        [
            ('morning', 'Morning (07:00 - 15:00)'),
            ('evening', 'Evening (15:00 - 23:00)'),
            ('night', 'Night (23:00 - 07:00)'),
        ],
        string='Initial Shift',required=True,
        help='Default shift applied when generating slots from this template.'
    )

    rotation_type = fields.Selection(
        [
            ('day', 'Day shift (07:00 - 15:00)'),
            ('two_shift', '2-shift rotating'),
            ('three_shift', '3-shift rotating'),
        ],
        string='Rotation Type',required=True,
        help='Defines how the shift rotates week by week for this template.'
    )

    def _check_duplicate_shift_template(self):
        Template = self.env['planning.slot.template']
        for template in self:
            if not (template.initial_shift and template.rotation_type and template.skill_ids):
                continue
            duplicate_candidates = Template.search([
                ('initial_shift', '=', template.initial_shift),
                ('rotation_type', '=', template.rotation_type),
                ('id', '!=', template.id),
            ])
            template_skill_ids = set(template.skill_ids.ids)
            for candidate in duplicate_candidates:
                if template_skill_ids == set(candidate.skill_ids.ids):
                    raise ValidationError('This shift template already exists.')

    @api.onchange('initial_shift')
    def _onchange_initial_shift(self):
        shift_hours = {
            'morning': (7.0, 15.0),
            'evening': (15.0, 23.0),
            'night': (23.0, 7.0),
        }
        shift_span = {
            'morning': 1,
            'evening': 1,
            'night': 2,
        }
        for template in self:
            hours = shift_hours.get(template.initial_shift)
            if not hours:
                continue
            template.start_time = hours[0]
            template.end_time = hours[1]
            template.duration_days = shift_span.get(template.initial_shift, 1)


    def _apply_template_shift_to_skill_employees(self):
        Employee = self.env['hr.employee']
        for template in self:
            if not template.skill_ids:
                continue

            vals = {}
            if template.initial_shift:
                vals['initial_shift'] = template.initial_shift
            if template.rotation_type:
                vals['rotation_type'] = template.rotation_type
            if not vals:
                continue

            resources = template.skill_ids.mapped('resource_ids')
            if not resources:
                continue

            employees = Employee.search([
                ('resource_id', 'in', resources.ids),
                ('priority_skill_id', 'in', template.skill_ids.ids),
            ])
            if not employees:
                continue

            employees.write(vals)

    def _get_template_skill_employees(self):
        Employee = self.env['hr.employee']
        mapping = {}
        for template in self:
            resources = template.skill_ids.mapped('resource_ids')
            if resources:
                employees = Employee.search([
                    ('resource_id', 'in', resources.ids),
                    ('priority_skill_id', 'in', template.skill_ids.ids),
                ])
            else:
                employees = Employee.browse()
            mapping[template] = employees
        return mapping

    def _generate_week_slots_for_templates(self, monday):
        for template, employees in self._get_template_skill_employees().items():
            if not employees:
                continue

            shift = template.initial_shift or 'morning'
            rotation_type = template.rotation_type or 'day'
            for employee in employees:
                employee.with_context(skip_initial_shift_generation=True).write({
                    'initial_shift': shift,
                    'rotation_type': rotation_type,
                })
            working_days = 4 if shift == 'night' else 5
            employees._generate_week_slots(monday, shift, working_days)

    @api.model
    def create(self, vals):
        template = super().create(vals)
        template._check_duplicate_shift_template()
        template._apply_template_shift_to_skill_employees()
        return template

    def write(self, vals):
        res = super().write(vals)
        self._check_duplicate_shift_template()
        trigger_fields = {'skill_ids', 'initial_shift', 'rotation_type'}
        if trigger_fields.intersection(vals.keys()):
            self._apply_template_shift_to_skill_employees()
        return res

    def cron_generate_template_shifts(self):
        today = fields.Date.context_today(self)
        monday = today - relativedelta(days=today.weekday())
        templates = self.search([('skill_ids', '!=', False)])
        templates._generate_week_slots_for_templates(monday)
