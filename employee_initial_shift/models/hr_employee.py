from datetime import datetime, time, timedelta
import pytz
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    initial_shift = fields.Selection(
        [
            ('morning', 'Morning (07:00 - 15:00)'),
            ('evening', 'Evening (15:00 - 23:00)'),
            ('night', 'Night (23:00 - 07:00)'),
        ],
        string='Initial Shift',
        help='Default shift for this employee.',
    )

    rotation_type = fields.Selection(
        [
            ('day', 'Day shift (07:00 - 15:00)'),
            ('two_shift', '2-shift rotating'),
            ('three_shift', '3-shift rotating'),
        ],
        string='Rotation Type',
        help='Defines how the shift rotates week by week.',
    )
    rotation_start_monday = fields.Date(
        string='Rotation Start Monday',
        help='Monday of the first rotation week; used to compute next weeks in the cycle.',
    )
    rotation_start_date = fields.Date(
        string='Rotation Start Date',
        related='rotation_start_monday',
        store=True,
    )

    priority_skill_id = fields.Many2one(
        'planning.skill',
        string='Priority Skill',
        help='Primary working skill for this employee. Only skills linked to this employee are allowed.',
    )

    @api.constrains('priority_skill_id', 'resource_id')
    def _check_priority_skill_assignment(self):
        for employee in self:
            if employee.priority_skill_id and employee.resource_id not in employee.priority_skill_id.resource_ids:
                raise ValidationError(
                    'Priority skill must be one of the skills assigned to this employee.'
                )

    def _generate_week_slots(self, monday, shift, working_days):
        """Generate planning slots for a given week starting on monday"""
        Planning = self.env['planning.slot']
        for employee in self:
            if not shift or not employee.resource_id:
                continue
            user_tz = pytz.timezone(
                employee.tz
                or (employee.company_id.resource_calendar_id and employee.company_id.resource_calendar_id.tz)
                or self.env.user.tz
                or 'UTC'
            )
            last_work_day = monday + relativedelta(days=working_days - 1)
            cleanup_start_day = monday - relativedelta(days=1) if shift == 'night' else monday
            cleanup_end_day = last_work_day + relativedelta(days=1)
            week_start_local = datetime.combine(cleanup_start_day, time.min)
            week_end_local = datetime.combine(cleanup_end_day, time.max)
            week_start_dt = user_tz.localize(week_start_local).astimezone(pytz.utc).replace(tzinfo=None)
            week_end_dt = user_tz.localize(week_end_local).astimezone(pytz.utc).replace(tzinfo=None)

            existing_slots = Planning.search([
                ('resource_id', '=', employee.resource_id.id),
                ('start_datetime', '>=', week_start_dt),
                ('start_datetime', '<=', week_end_dt),
            ])
            existing_slots.unlink()

            if shift == 'morning':
                start_hour, end_hour = 7, 15
                label = 'Morning Shift'
            elif shift == 'evening':
                start_hour, end_hour = 15, 23
                label = 'Evening Shift'
            else:
                start_hour = end_hour = None
                label = 'Night Shift'

            for i in range(working_days):
                day = monday + relativedelta(days=i)
                if shift == 'night':
                    previous_day = day - relativedelta(days=1)
                    start_local = datetime.combine(previous_day, time(23, 0))
                    end_local = datetime.combine(day, time(7, 0))
                else:
                    start_local = datetime.combine(day, time(start_hour, 0))
                    end_local = datetime.combine(day, time(end_hour, 0))

                start_dt = user_tz.localize(start_local).astimezone(pytz.utc).replace(tzinfo=None)
                end_dt = user_tz.localize(end_local).astimezone(pytz.utc).replace(tzinfo=None)

                Planning.create({
                    'resource_id': employee.resource_id.id,
                    'start_datetime': start_dt,
                    'end_datetime': end_dt,
                    'company_id': employee.company_id.id,
                    'state': 'published',
                    'name': label,
                })

    def _generate_initial_shift_week_slots(self):
        today = fields.Date.context_today(self)
        weekday = today.weekday()  # Monday = 0
        monday = today - relativedelta(days=weekday)
        for employee in self:
            if employee.initial_shift and employee.resource_id:
                working_days = 4 if employee.initial_shift == 'night' else 5
                if employee.rotation_type in ('two_shift', 'three_shift'):
                    if employee.rotation_type == 'two_shift':
                        desired_cycle = 0 if employee.initial_shift == 'morning' else 1
                    else:
                        if employee.initial_shift == 'morning':
                            desired_cycle = 0
                        elif employee.initial_shift == 'evening':
                            desired_cycle = 1
                        else:
                            desired_cycle = 2
                    start_monday = monday - relativedelta(weeks=desired_cycle)
                    employee.with_context(skip_rotation_start_update=True).write({
                        'rotation_start_monday': start_monday,
                    })

                employee._generate_week_slots(monday, employee.initial_shift, working_days)

    @api.model
    def create(self, vals):
        employees = super().create(vals)
        if vals.get('rotation_type') and not vals.get('rotation_start_monday'):
            today = fields.Date.context_today(employees)
            weekday = today.weekday()
            monday = today - relativedelta(days=weekday)
            employees.write({'rotation_start_monday': monday})

        employees._generate_initial_shift_week_slots()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if 'rotation_type' in vals and not self.env.context.get('skip_rotation_start_update'):
            for employee in self:
                if employee.rotation_type and not employee.rotation_start_monday:
                    today = fields.Date.context_today(employee)
                    weekday = today.weekday()
                    monday = today - relativedelta(days=weekday)
                    employee.rotation_start_monday = monday

        if 'initial_shift' in vals and not self.env.context.get('skip_initial_shift_generation'):
            self._generate_initial_shift_week_slots()
        return res

    @api.model
    def cron_generate_next_week_shifts(self):
        """Weekly cron to generate next week's shifts based on rotation_type."""

        today = fields.Date.context_today(self)
        weekday = today.weekday()
        delta_days = 7 - weekday or 7
        # next_monday = today + relativedelta(days=delta_days)
        next_monday = today + relativedelta(days=delta_days + 14)
        employees = self.search([('rotation_type', '!=', False), ('resource_id', '!=', False)])
        for employee in employees:
            start_monday = employee.rotation_start_monday
            if not start_monday:
                emp_weekday = today.weekday()
                start_monday = today - relativedelta(days=emp_weekday)
                employee.with_context(skip_rotation_start_update=True).write({
                    'rotation_start_monday': start_monday,
                })

            weeks_since_start = (next_monday - start_monday).days // 7
            shift = 'morning'
            working_days = 5
            if employee.rotation_type == 'day':
                shift = 'morning'
                working_days = 5
            elif employee.rotation_type == 'two_shift':
                cycle_week = weeks_since_start % 2
                shift = 'morning' if cycle_week == 0 else 'evening'
                working_days = 5
            elif employee.rotation_type == 'three_shift':
                cycle_week = weeks_since_start % 3
                if cycle_week == 0:
                    shift = 'morning'
                    working_days = 5
                elif cycle_week == 1:
                    shift = 'evening'
                    working_days = 5
                else:
                    shift = 'night'
                    working_days = 4

            employee.with_context(skip_initial_shift_generation=True).write({'initial_shift': shift})
            employee._generate_week_slots(next_monday, shift, working_days)