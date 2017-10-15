# -*- encoding: utf-8 -*-
from openerp import api, fields, models, _
from openerp.exceptions import UserError, RedirectWarning, ValidationError
import base64

#DATES
from datetime import datetime, timedelta
import pytz
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

class SaleLoadWizard(models.TransientModel):
    _name = 'sale.load.wizard'


    txt_file = fields.Binary(string='Archivo (*.txt)',
                    filters='*.txt', 
                    help='Seleccione el archivo a cargar (*.txt)')

    def get_source(self):
        source = False
        res = self.env['utm.source'].search([('name', '=', 'Edi Local')])
        if len(res) > 0:
            source = res[0]
            return source.id
        return False

    def search_partner(self,ref):
        partner = False
        po = self.env['res.partner']
        res = po.search([('ref', '=', ref)])
        if len(res) > 0:
            partner = res[0]

        if partner == False:
            raise ValidationError(_('Partner not found, ref: '+ref))

        return partner

    def search_product(self,ref):
        product = False
        pp = self.env['product.product']
        res = pp.search([('default_code', '=', ref)])
        if len(res) > 0:
            product = res[0]

        if product == False:
            raise ValidationError(_('Product not found, ref: '+ref))

        return product

    def convert_strdate_toserver(self,date):
        date = datetime.strptime(date, "%d/%m/%Y")
        #print 'type(date): ',type(date)
        #user_tz = self.env.user.tz or pytz.utc
        user_tz = pytz.timezone(self.env.user.tz) or pytz.utc
        
        #print 'user_tz: ',user_tz
        date = user_tz.localize(date)
        #commitment_date = datetime(commitment_date, user_tz)

        #CONVERT TO UTC
        date = date.astimezone(pytz.utc)
        #print 'date!!!: ',date
        return date

    def action_load(self):
        """
        reads file and loads sale orders
        """
        so = self.env['sale.order']
        afp = self.env['account.fiscal.position']
        so_fields = [] #WILL CONTAIN FIELDS FOR SALE ORDER, EACH ELEMENT IS A SALE ORDER
        order_lines = []
        fields = {}
        source = self.get_source()
        file_txt = base64.decodestring(self.txt_file)
        line_n = 1 #LINE NUMBER

        for line in file_txt.splitlines():
            elements = line.split()
    
            if len(elements) > 0:
                if elements[0] == 'R':

                    if line_n > 1:
                        fields['order_line'] = order_lines
                        so_fields.append(fields)

                        fields = {}
                        order_lines = []
                        #so.create(fields)

                    partner_ref = elements[1]
                    partner = self.search_partner(partner_ref)

                    #GET FISCAL POSITION
                    addr = partner.address_get(['delivery', 'invoice'])
                    fiscal_position_id = afp.get_fiscal_position(partner.id, addr['delivery'])

                    order_name = elements[2]
                    commitment_date = elements[3]

                    #ASIGN USERS TIMEZONE TO DATE
                    #"%Y-%m-%d %H:%M:%S"
                    commitment_date =self.convert_strdate_toserver(commitment_date)

                    #raise ValidationError(_('!!!!'))

                    fields = {
                        'name':order_name,
                        'partner_id':partner.id,
                        'fiscal_position_id':fiscal_position_id,
                        'pricelist_id': partner.property_product_pricelist and partner.property_product_pricelist.id or False,
                        'payment_term_id': partner.property_payment_term_id and partner.property_payment_term_id.id or False,
                        'pay_method_id': partner.pay_method_id and partner.pay_method_id.id or False,
                        'source_id': source,
                        'commitment_date': commitment_date,
                    }
                else: 
                    product_qty = elements[0]
                    product_ref = elements[1]
                    product = self.search_product(product_ref)

                    line_fields = {
                        'product_id':product.id,
                        'product_uom_qty':product_qty,
                    }

                    order_lines.append((0,0,line_fields))
            line_n += 1

        #SE AGREGA LA ULTIMA SO
        fields = {
            'name':order_name,
            'partner_id':partner.id,
            'fiscal_position_id':fiscal_position_id,
            'pricelist_id': partner.property_product_pricelist and partner.property_product_pricelist.id or False,
            'payment_term_id': partner.property_payment_term_id and partner.property_payment_term_id.id or False,
            'pay_method_id': partner.pay_method_id and partner.pay_method_id.id or False,
            'source_id': source,
            'commitment_date': commitment_date,
            'order_line':order_lines,
        }
        so_fields.append(fields)

        #CREATE NEW SALE ORDERS
        sale_orders = map(lambda fields:so.create(fields), so_fields)

        #print 'sale_orders: ',sale_orders
        #CONFIRM SO
        map(lambda order:self.action_load_confirm(order), sale_orders)
        

        return {
                'name'      : _('Quotations'),
                'view_mode': 'tree,form',
                'view_type': 'form',
                'res_model': 'sale.order',
                'type': 'ir.actions.act_window',
            }
        

    def action_load_confirm(self,order):
        order.state = 'sale'
        order.confirmation_date = fields.Datetime.now()
        # if self.env.context.get('send_email'):
        #     self.force_quotation_send()
        order.order_line._action_procurement_create()
        if self.env['ir.values'].get_default('sale.config.settings', 'auto_done_setting'):
            order.action_done()
        return True