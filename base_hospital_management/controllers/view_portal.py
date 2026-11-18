# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Subina P (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
from odoo import http
from odoo.http import request


class ViewPortal(http.Controller):
    """Standard /my portal pages of the base module.

    SECURITY FIX: the original routes were auth="public" and
    /my/tests/<id> browsed ANY lab test with sudo(), so anybody could read
    any patient's results by changing the number in the URL. Now:
      * auth="user"  -> only logged-in users,
      * every search is filtered on the logged-in user's own partner,
      * the raw SQL on ir_attachment was replaced by an ORM search.
    """

    def _partner(self):
        return request.env.user.partner_id

    def _first_attachment(self, model, res_id):
        attachment = request.env['ir.attachment'].sudo().search(
            [('res_model', '=', model), ('res_id', '=', res_id)], limit=1)
        return attachment.id or False

    @http.route('/my/vaccinations', type='http', auth="user", website=True)
    def portal_my_vaccine(self, **kw):
        """Function for rendering vaccination details of portal user"""
        vaccination_list = []
        for rec in request.env['hospital.vaccination'].sudo().search(
                [('patient_id', '=', self._partner().id)]):
            vaccination_list.append({
                'id': rec.id,
                'name': rec.name,
                'vaccine_date': rec.vaccine_date,
                'dose': rec.dose,
                'vaccine_product_id': rec.vaccine_product_id.name,
                'vaccine_price': rec.vaccine_price,
                'attachment_id': self._first_attachment(
                    'hospital.vaccination', rec.id),
            })
        values = {
            'vaccinations': vaccination_list,
            'page_name': 'vaccination'
        }
        return request.render("base_hospital_management.portal_my_vaccines",
                              values)

    @http.route(['/my/tests'], type='http', auth="user", website=True)
    def portal_my_tests(self, **kw):
        """Function for rendering tests of portal user"""
        tests_list = []
        for rec in request.env['patient.lab.test'].sudo().search(
                [('patient_id', '=', self._partner().id)]):
            tests_list.append({
                'id': rec.id,
                'name': rec.test_id.name,
                'date': rec.date
            })
        values = {
            'tests': tests_list,
            'page_name': 'lab_test'
        }
        return request.render("base_hospital_management.portal_my_tests",
                              values)

    @http.route('/my/tests/<int:test_id>', type="http", auth="user",
                website=True)
    def tests_view(self, test_id, **kw):
        """Function for rendering test results of portal user"""
        all_test = request.env['patient.lab.test'].sudo().search(
            [('id', '=', test_id), ('patient_id', '=', self._partner().id)],
            limit=1)
        if not all_test:
            return request.not_found()
        result_list = []
        for rec in all_test.result_ids:
            result_list.append({
                'id': rec.id,
                'name': rec.test_id.name,
                'result': rec.result,
                'price': rec.price,
                'attachment_id': self._first_attachment(
                    'lab.test.result', rec.id),
            })
        values = {
            'all_test_id': all_test.id,
            'results': result_list,
            'page_name': 'test_results'
        }
        return request.render(
            "base_hospital_management.portal_my_tests_results", values)

    @http.route('/my/op', type='http', auth="user", website=True)
    def portal_my_op(self, **kw):
        """Function for rendering prescriptions of portal user"""
        op = request.env['hospital.outpatient'].sudo().search_read(
            [('patient_id', '=', self._partner().id)],
            ['op_reference', 'op_date', 'doctor_id', 'slot',
             'prescription_ids'])
        for record in op:
            hours = int(record['slot'])
            minutes = int((record['slot'] - hours) * 60)
            record['slot'] = '{:02d}:{:02d}'.format(hours, minutes)
        values = {
            'op': op,
            'page_name': 'op'
        }
        return request.render(
            "base_hospital_management.portal_my_op", values)