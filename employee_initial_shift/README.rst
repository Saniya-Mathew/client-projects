Employee Initial Shift
=======================

Overview
--------
The **Employee Initial Shift** module extends Odoo's Human Resources and Planning applications by letting HR managers define a default shift and rotation pattern per employee. Planning slots are generated automatically so that each worker's first week—and any future rotations—always follow the defined schedule.

Key Features
------------
* **Initial shift selection**: Assign Morning (07:00d15:00), Evening (15:00d23:00), or Night (23:00d07:00) directly on the employee form.
* **Rotation policies**: Choose between a fixed Day shift, a 2-shift rotation (Morning/Evening), or a 3-shift rotation (Morning/Evening/Night). The module stores the reference Monday that starts the rotation cycle.
* **Automatic planning slots**:
  - On employee creation and whenever the initial shift changes, the current week's planning slots are regenerated based on the chosen shift and working days (4 days for night, 5 days for others).
  - Existing slots for the same resource and week are cleaned up before new ones are created, preventing duplicates.
* **Weekly cron**: The *Employee Shift Rotation* scheduled action calls ``cron_generate_next_week_shifts`` every week to:
  - Determine the upcoming week's shift for each rotating employee.
  - Update the employee's ``initial_shift`` to the next shift in the cycle.
  - Generate fresh planning slots for the following week.
* **Planning search helpers**: Adds quick filters and a Group By option to the planning search view to track slots by the employee's initial shift.

Configuration
-------------
1. **Dependencies**: Ensure the ``hr`` and ``planning`` modules are installed (declared in ``__manifest__.py``).
2. **Access rights**: Users need HR permissions to edit employees and planning permissions to view generated slots.
3. **Cron activation**: The scheduled action defined in ``data/shift_rotation_cron.xml`` is active by default. Adjust the interval or deactivate it from *Settings > Technical > Automation > Scheduled Actions* if needed.

Usage
-----
1. Navigate to *Employees > Employees* and open an employee record.
2. Set **Initial Shift** and optionally **Rotation Type**:
   * For rotating shifts, the module aligns ``rotation_start_monday`` automatically so that the selected initial shift is the first week in the cycle.
3. Save the record. Planning slots for the current week are generated immediately.
4. Review generated slots in *Planning > Planning*, where you can use the new **Morning/Evening/Night** filters or group by *Initial Shift* to visualize workforce distribution.

Technical Notes
---------------
* The ``hr.employee`` model gains:
  - ``initial_shift`` (selection)
  - ``rotation_type`` (selection)
  - ``rotation_start_monday`` (date)
  - Helper methods ``_generate_week_slots`` and ``_generate_initial_shift_week_slots``.
* ``planning.slot`` stores ``employee_initial_shift`` as a related field, enabling reporting and filters.
* Timezone-aware slot creation ensures shifts align with each employee's timezone or company calendar.
* When rotation data is missing, the cron aligns ``rotation_start_monday`` with the current week to keep cycles consistent.

Troubleshooting & Tips
----------------------
* If planning slots are not appearing, confirm the employee has a linked resource (standard Odoo requirement for planning).
* Night shifts are created as 4 consecutive days with 23:00d07:00 coverage. Adjust the logic in ``models/hr_employee.py`` if your organization uses different patterns.
* To support custom shifts or longer cycles, extend the selection values and rotation logic in ``cron_generate_next_week_shifts``.
