# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from openerp import api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    manufacturer_product_name = fields.Char('Codigo EDI')
    manufacturer_product_ref = fields.Integer('Empaque EDI',size=5)
    #manufacturer_product_type = fields.Selection('Tipo EDI')

    manufacturer_product_type = fields.Selection(
                [('A','A'),
                ('M','M'),
                ('P','P'),
                ],
                'Tipo EDI', default='A')