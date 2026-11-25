from odoo import http, fields, _
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class PerformancePortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        user = request.env.user

        if 'goal_count' in counters:
            values['goal_count'] = request.env['hr.performance.goal'].search_count([
                ('employee_id.user_id', '=', user.id),
            ])
        if 'scorecard_count' in counters:
            values['scorecard_count'] = request.env['hr.final.scorecard'].search_count([
                ('employee_id.user_id', '=', user.id),
            ])
        if 'coaching_count' in counters:
            values['coaching_count'] = request.env['hr.coaching.session'].search_count([
                ('employee_id.user_id', '=', user.id),
            ])
        if 'pip_count' in counters:
            values['pip_count'] = request.env['hr.performance.improvement.plan'].search_count([
                ('employee_id.user_id', '=', user.id),
            ])
        if 'evaluation_count' in counters:
            tech_count = request.env['hr.technical.evaluation'].search_count([
                ('evaluator_id.user_id', '=', user.id),
            ])
            behav_count = request.env['hr.behavioural.evaluation'].search_count([
                ('evaluator_id.user_id', '=', user.id),
            ])
            values['evaluation_count'] = tech_count + behav_count
        return values

    def _check_employee_record(self, model_name, res_id):
        record = request.env[model_name].browse(res_id)
        if not record.exists():
            raise MissingError(_("Record not found."))
        record.check_access('read')
        return record

    # ------------------------------------------------------------------
    # Goals
    # ------------------------------------------------------------------
    @http.route(['/my/performance/goals', '/my/performance/goals/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_goals(self, page=1, **kw):
        Goal = request.env['hr.performance.goal']
        domain = [('employee_id.user_id', '=', request.env.user.id)]
        total = Goal.search_count(domain)
        pager = portal_pager(
            url='/my/performance/goals',
            total=total,
            page=page,
            step=20,
        )
        goals = Goal.search(domain, order='start_date desc, id desc', limit=20, offset=pager['offset'])
        return request.render('hr_performance_management.portal_my_goals', {
            'goals': goals,
            'page_name': 'performance_goals',
            'pager': pager,
        })

    @http.route('/my/performance/goals/<int:goal_id>', type='http', auth='user', website=True)
    def portal_my_goal_detail(self, goal_id, **kw):
        try:
            goal = self._check_employee_record('hr.performance.goal', goal_id)
        except (AccessError, MissingError):
            return request.redirect('/my/performance/goals')
        return request.render('hr_performance_management.portal_my_goal_detail', {
            'goal': goal,
            'page_name': 'performance_goal_detail',
            'error': kw.get('error'),
            'message': kw.get('message'),
        })

    @http.route('/my/performance/goals/<int:goal_id>/respond', type='http', auth='user',
                methods=['POST'], website=True)
    def portal_my_goal_respond(self, goal_id, action_type=None, employee_comments='', **kw):
        goal = self._check_employee_record('hr.performance.goal', goal_id)
        if employee_comments:
            goal.employee_comments = employee_comments
        try:
            if action_type == 'agree':
                goal.action_employee_agree()
            elif action_type == 'modify':
                goal.action_employee_request_modification()
        except ValidationError as exc:
            return request.redirect(f'/my/performance/goals/{goal.id}?error={exc}')
        return request.redirect(f'/my/performance/goals/{goal.id}?message=updated')

    @http.route('/my/performance/goals/<int:goal_id>/progress', type='http', auth='user',
                methods=['POST'], website=True)
    def portal_my_goal_progress(self, goal_id, progress_percentage=0, achievements='',
                                challenges='', support_required='', **kw):
        goal = self._check_employee_record('hr.performance.goal', goal_id)
        try:
            pct = float(progress_percentage or 0)
            request.env['hr.goal.progress.update'].create({
                'goal_id': goal.id,
                'date_updated': fields.Date.context_today(goal),
                'progress_percentage': pct,
                'achievements': achievements,
                'challenges': challenges,
                'support_required': support_required,
            })
        except (ValueError, ValidationError) as exc:
            return request.redirect(f'/my/performance/goals/{goal.id}?error={exc}')
        return request.redirect(f'/my/performance/goals/{goal.id}?message=progress_added')

    # ------------------------------------------------------------------
    # Scorecards
    # ------------------------------------------------------------------
    @http.route(['/my/performance/scorecards', '/my/performance/scorecards/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_scorecards(self, page=1, **kw):
        Scorecard = request.env['hr.final.scorecard']
        domain = [('employee_id.user_id', '=', request.env.user.id)]
        total = Scorecard.search_count(domain)
        pager = portal_pager(
            url='/my/performance/scorecards',
            total=total,
            page=page,
            step=20,
        )
        scorecards = Scorecard.search(domain, order='id desc', limit=20, offset=pager['offset'])
        return request.render('hr_performance_management.portal_my_scorecards', {
            'scorecards': scorecards,
            'page_name': 'performance_scorecards',
            'pager': pager,
        })

    @http.route('/my/performance/scorecards/<int:scorecard_id>', type='http', auth='user', website=True)
    def portal_my_scorecard_detail(self, scorecard_id, **kw):
        try:
            scorecard = self._check_employee_record('hr.final.scorecard', scorecard_id)
        except (AccessError, MissingError):
            return request.redirect('/my/performance/scorecards')
        return request.render('hr_performance_management.portal_my_scorecard_detail', {
            'scorecard': scorecard,
            'page_name': 'performance_scorecard_detail',
            'error': kw.get('error'),
            'message': kw.get('message'),
        })

    @http.route('/my/performance/scorecards/<int:scorecard_id>/acknowledge', type='http', auth='user',
                methods=['POST'], website=True)
    def portal_my_scorecard_acknowledge(self, scorecard_id, action_type=None,
                                        employee_comments='', **kw):
        scorecard = self._check_employee_record('hr.final.scorecard', scorecard_id)
        if employee_comments:
            scorecard.employee_comments = employee_comments
        try:
            if action_type == 'accept':
                scorecard.action_employee_accept()
            elif action_type == 'appeal':
                scorecard.action_employee_appeal()
        except ValidationError as exc:
            return request.redirect(f'/my/performance/scorecards/{scorecard.id}?error={exc}')
        return request.redirect(f'/my/performance/scorecards/{scorecard.id}?message=updated')

    # ------------------------------------------------------------------
    # Coaching Sessions & PIPs
    # ------------------------------------------------------------------
    @http.route('/my/performance/coaching', type='http', auth='user', website=True)
    def portal_my_coaching(self, **kw):
        sessions = request.env['hr.coaching.session'].search([
            ('employee_id.user_id', '=', request.env.user.id),
        ], order='meeting_date desc')
        return request.render('hr_performance_management.portal_my_coaching', {
            'sessions': sessions,
            'page_name': 'performance_coaching',
        })

    @http.route('/my/performance/pips', type='http', auth='user', website=True)
    def portal_my_pips(self, **kw):
        pips = request.env['hr.performance.improvement.plan'].search([
            ('employee_id.user_id', '=', request.env.user.id),
        ], order='start_date desc')
        return request.render('hr_performance_management.portal_my_pips', {
            'pips': pips,
            'page_name': 'performance_pips',
        })

    # ------------------------------------------------------------------
    # Assigned Evaluations (when user is an evaluator)
    # ------------------------------------------------------------------
    @http.route('/my/performance/evaluations', type='http', auth='user', website=True)
    def portal_my_evaluations(self, **kw):
        uid = request.env.user.id
        tech_evals = request.env['hr.technical.evaluation'].search([
            ('evaluator_id.user_id', '=', uid),
        ], order='id desc')
        behav_evals = request.env['hr.behavioural.evaluation'].search([
            ('evaluator_id.user_id', '=', uid),
        ], order='id desc')
        return request.render('hr_performance_management.portal_my_evaluations', {
            'tech_evals': tech_evals,
            'behav_evals': behav_evals,
            'page_name': 'performance_evaluations',
        })
