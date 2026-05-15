from odoo import models, fields, api
import datetime

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # Custom fields translated to English [cite: 201-204]
    solution = fields.Text(string="Solution")
    send_email_on_resolve = fields.Boolean(string="Send Email on Resolve?")
    reason_on_hold = fields.Text(string="Reason On Hold")
    send_email_on_hold = fields.Boolean(string="Send Email on Hold?")

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super(HelpdeskTicket, self).create(vals_list)
        for ticket in tickets:
            ticket._apply_keyword_automation()
        return tickets

    def write(self, vals):
        # Auto-assignment: If stage changes to 'In Progress' (e.g., ID 2), assign to current user
        # Note: Replace '2' with the actual ID of your 'In Progress' stage if it differs.
        if vals.get('stage_id') == 2 and self.env.user:
            vals['user_id'] = self.env.user.id

        res = super(HelpdeskTicket, self).write(vals)
        
        # Trigger keyword scan if name or description is updated [cite: 280-281, 356]
        if 'name' in vals or 'description' in vals:
            for ticket in self:
                ticket._apply_keyword_automation()
                
        return res

    def _apply_keyword_automation(self):
        """ Automatically tags and updates priority based on keywords. """
        for record in self:
            # Note: Keywords kept in Dutch to match incoming client emails [cite: 287-288, 362-366]
            tag_mapping = {
                'Unemployment': ['werkloosheid', 'economische werkloosheid'],
                'Request': ['nieuwe werknemer'],
                'Payroll': ['lonen', 'correctie', 'prestaties', 'c4', 'dimona'],
                'Bad Weather': ['weerverlet', 'slecht weer'],
                'Social Security': ['rsz', 'sociale zekerheid', 'onss']
            }
            
            prio_keywords = ['c4', 'dimona', 'weerverlet', 'slecht weer', 'werkloosheid', 'rsz']
            
            subject = (record.name or '').lower()
            description = (record.description or '').lower()
            combined_text = f"{subject} {description}"

            tags_to_add = []
            for tag_name, keywords in tag_mapping.items():
                if any(word in combined_text for word in keywords):
                    tag = self.env['helpdesk.tag'].search([('name', '=ilike', tag_name)], limit=1)
                    if not tag:
                        tag = self.env['helpdesk.tag'].create({'name': tag_name})
                    if tag.id not in record.tag_ids.ids:
                        tags_to_add.append(tag.id)

            vals = {}
            if tags_to_add:
                vals['tag_ids'] = [(4, tid) for tid in tags_to_add] # 4 = link to existing record [cite: 388, 390]

            if any(word in combined_text for word in prio_keywords):
                if record.priority != '1':
                    vals['priority'] = '1'
                    record._message_log(body="<b>Automation:</b> Keyword detected. Tags and priority automatically updated.") # [cite: 306, 396]

            if vals:
                record.write(vals)

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        """ Intercepts messages for Customer Replies and Agent Public Comments """
        message = super(HelpdeskTicket, self).message_post(**kwargs)
        
        for ticket in self:
            # 1. Customer Reply Logic (Inbound Mail) [cite: 312-314]
            if message.author_id != self.env.user.partner_id and (datetime.datetime.now() - ticket.create_date).total_seconds() > 120:
                current_owner_id = ticket.user_id.id
                recipient = current_owner_id or 69 # Fallback user ID if unassigned [cite: 328]

                # Schedule activity [cite: 330-335]
                ticket.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary='New customer reply',
                    note='The customer has replied. Action required.',
                    user_id=recipient,
                    date_deadline=datetime.date.today()
                )

                # Move from 'Waiting on Customer' (e.g., ID 3) to 'In Progress' (e.g., ID 2) [cite: 338-340, 349]
                if ticket.stage_id.id == 3:
                    ticket.sudo().write({'stage_id': 2})
                    if current_owner_id:
                        # Double write to overwrite OdooBot auto-assignment [cite: 321, 341-343]
                        ticket.sudo().write({'user_id': current_owner_id})

            # 2. Agent Public Comment Logic [cite: 401-403]
            comment_subtype = self.env.ref('mail.mt_comment')
            if ticket.stage_id.name == 'New' and message.subtype_id == comment_subtype: # [cite: 408, 412-415]
                new_stage = self.env['helpdesk.stage'].search([
                    ('name', '=', 'In Progress'), # [cite: 417-419]
                    ('team_ids', 'in', ticket.team_id.ids)
                ], limit=1)
                
                if new_stage:
                    ticket.write({'stage_id': new_stage.id})

        return message

    @api.model
    def _cron_close_resolved_tickets(self):
        """ Cron action: Change 'Resolved' tickets to 'Closed' after 7 days """
        seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        tickets = self.search([
            ('stage_id.name', '=', 'Resolved'), # [cite: 230]
            ('write_date', '<', seven_days_ago)
        ])
        if tickets:
            closed_stage = self.env['helpdesk.stage'].search([('name', '=', 'Closed')], limit=1) # [cite: 231]
            if closed_stage:
                tickets.write({'stage_id': closed_stage.id})