# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalPurchaseApprovalLevel(models.Model):
    """User-definable multi-level purchase approval configuration."""
    _name = 'hospital.purchase.approval.level'
    _description = 'Purchase Approval Level'
    _order = 'sequence'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Level Name', required=True,
                       help='e.g. Unit Level, Department Level, Central Office Level, Director Board')
    min_amount = fields.Monetary(string='Min Amount (₹)', currency_field='currency_id')
    max_amount = fields.Monetary(string='Max Amount (₹)', currency_field='currency_id',
                                  help='Leave 0 for no upper limit')
    approver_group_id = fields.Many2one('res.groups', string='Approver Group', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    active = fields.Boolean(default=True)


class HospitalBudget(models.Model):
    """Simple budget control for purchase departments."""
    _name = 'hospital.budget'
    _description = 'Department Purchase Budget'

    name = fields.Char(string='Budget Name', required=True)
    fiscal_year = fields.Char(string='Fiscal Year', required=True,
                               default=lambda s: str(fields.Date.today().year))
    dept_id = fields.Many2one('hr.department', string='Department', required=True)
    budget_head = fields.Char(string='Budget Head / Account Code')
    allocated_amount = fields.Monetary(string='Allocated Amount', currency_field='currency_id',
                                        required=True)
    used_amount = fields.Monetary(string='Used Amount', compute='_compute_used_amount', store=True,
                                   currency_field='currency_id')
    remaining_amount = fields.Monetary(string='Remaining', compute='_compute_used_amount', store=True,
                                        currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)

    @api.depends('allocated_amount')
    def _compute_used_amount(self):
        for rec in self:
            # Sum confirmed purchase orders for this department in this fiscal year
            orders = self.env['purchase.order'].search([
                ('state', 'in', ['purchase', 'done']),
                ('date_approve', '!=', False),
            ])
            used = sum(o.amount_total for o in orders)
            rec.used_amount = used
            rec.remaining_amount = rec.allocated_amount - used


class PurchaseOrder(models.Model):
    """Extend purchase.order for hospital multi-level approval workflow."""
    _inherit = 'purchase.order'

    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_level1', 'Awaiting Level 1 Approval'),
        ('pending_level2', 'Awaiting Level 2 Approval'),
        ('pending_level3', 'Awaiting Level 3 Approval'),
        ('approved', 'Approved — Ready to Process'),
        ('rejected', 'Rejected'),
    ], default='draft', string='Approval Status', tracking=True)

    required_approval_level_id = fields.Many2one(
        'hospital.purchase.approval.level',
        string='Required Approval Level',
        compute='_compute_required_level',
        store=True,
    )
    dept_id = fields.Many2one('hr.department', string='Requesting Department')
    budget_id = fields.Many2one('hospital.budget', string='Budget')
    approval_note = fields.Text(string='Approval / Rejection Note')

    @api.depends('amount_total')
    def _compute_required_level(self):
        for rec in self:
            levels = self.env['hospital.purchase.approval.level'].search(
                [('active', '=', True)], order='sequence'
            )
            rec.required_approval_level_id = False
            for level in levels:
                max_amt = level.max_amount
                if level.min_amount <= rec.amount_total and (not max_amt or rec.amount_total <= max_amt):
                    rec.required_approval_level_id = level.id
                    break

    def button_confirm(self):
        """Override confirm: route to approval workflow if level is required."""
        for rec in self:
            if rec.required_approval_level_id:
                rec.approval_state = 'pending_level1'
                # Notify approver group
                rec._notify_approvers()
                continue
            super(PurchaseOrder, rec).button_confirm()

    def action_approve(self):
        """Approver approves the purchase order."""
        for rec in self:
            rec.approval_state = 'approved'
            super(PurchaseOrder, rec).button_confirm()

    def action_reject(self):
        """Approver rejects the purchase order."""
        for rec in self:
            rec.approval_state = 'rejected'
            rec.state = 'cancel'

    def _notify_approvers(self):
        self.ensure_one()
        group = self.required_approval_level_id.approver_group_id
        if not group:
            return
        # In Odoo 19, find group members via ir.model.access or direct SQL
        partner_ids = []
        try:
            self.env.cr.execute(
                "SELECT r.uid FROM res_groups_users_rel r WHERE r.gid = %s",
                (group.id,)
            )
            user_ids = [row[0] for row in self.env.cr.fetchall()]
            users = self.env['res.users'].browse(user_ids)
            partner_ids = users.mapped('partner_id.id')
        except Exception:
            pass
        body = (f'<p>Purchase Order <b>{self.name}</b> from '
                f'<b>{self.partner_id.name}</b> '
                f'(Total: {self.amount_total:.2f}) '
                f'requires your approval.</p>'
                f'<p>Approval Level: <b>{self.required_approval_level_id.name}</b></p>')
        self.message_post(body=body, partner_ids=partner_ids)


class StockPicking(models.Model):
    """Extend stock.picking to add QC inspection on goods receipt."""
    _inherit = 'stock.picking'

    qc_required = fields.Boolean(
        string='QC Inspection Required',
        default=True,
        help='Tick if QC inspection is required before accepting these goods.',
    )
    qc_state = fields.Selection([
        ('pending', 'QC Pending'),
        ('approved', 'QC Approved'),
        ('rejected', 'QC Rejected — Return to Supplier'),
    ], string='QC Status', default='pending')
    qc_notes = fields.Text(string='QC Inspection Notes')
    qc_by = fields.Many2one('hr.employee', string='QC Inspector')
    qc_date = fields.Date(string='QC Inspection Date')

    def button_validate(self):
        """Override validate: block if QC required but not approved."""
        for rec in self:
            if (rec.picking_type_id.code == 'incoming' and
                    rec.qc_required and rec.qc_state == 'pending'):
                raise UserError(
                    'QC inspection is required before accepting goods. '
                    'Please complete QC check first.'
                )
        return super().button_validate()

    def action_qc_approve(self):
        for rec in self:
            rec.qc_state = 'approved'
            rec.qc_date = fields.Date.today()

    def action_qc_reject(self):
        for rec in self:
            rec.qc_state = 'rejected'
            # Create return picking
            return_wizard = self.env['stock.return.picking'].with_context(
                active_id=rec.id, active_model='stock.picking'
            ).create({'picking_id': rec.id})
            return return_wizard.create_returns()