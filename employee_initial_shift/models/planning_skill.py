from odoo import fields, models


class PlanningSkill(models.Model):
    _name = 'planning.skill'
    _description = 'Planning Skill'

    name = fields.Char(required=True)
    resource_ids = fields.Many2many(
        'resource.resource',
        'planning_skill_resource_rel',
        'skill_id',
        'resource_id',
        string='Resources'
    )
