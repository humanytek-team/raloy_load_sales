# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp import api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    edi_load = fields.Boolean('Edi load',help='If checked, appears as an option for sale loads')

