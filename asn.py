# -*- encoding: utf-8 -*-
from openerp import api, fields, models, _
from openerp.exceptions import UserError, RedirectWarning, ValidationError
import base64
from datetime import datetime, timedelta, date

##### ENCODING
import unicodedata
import sys
reload(sys)  
sys.setdefaultencoding('utf8')

#time
import pytz
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

class SaleAsnWizard(models.TransientModel):
    _name = 'sale.asn.wizard'
    #_description = 'ASN Wizard'


    datas_fname = fields.Char('File Name',size=256)
    file = fields.Binary('Layout')
    download_file = fields.Boolean('Download')
    cadena_decoding = fields.Text('Binary')

    #company_id = fields.Many2one('res.company', 'Compania', default=lambda self: self.env.user.company_id, required=True)
    partner_id = fields.Many2one('res.partner', 'Partner', domain="[('edi_load', '=', True)]", required=True)
    start_date = fields.Date("Start date", required=True)
    end_date = fields.Date("End date", required=True)



    def format_element(self,size,element='',filler=' ',f_side=True):
        """
        size: desired element lenght
        element: string
        filler: string which will fill the element
        f_side: True - filler to the right, False - filler to the left
        """
        element = str(element)
        lenght = len(element)
        filler = str(filler)
        size = int(size)
        new_element = ''
        fillers = ''

        for x in range(0,(size-lenght)):
            fillers = fillers + filler

        if f_side:
            new_element = element + fillers
        else:
            new_element = fillers + element
        return new_element


    def convert_tz(self, date, format="%Y-%m-%d %H:%M:%S"):
        """
        converts date to user's timezone
        """
        user_tz = self.env.user.tz or pytz.utc
        local = pytz.timezone(user_tz)
        display_date_result = datetime.strftime(pytz.utc.localize(datetime.strptime(date,
        DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),format) 
        return display_date_result

    def calculate(self):
        partner = self.partner_id
        start_date = self.start_date
        end_date = self.end_date
        data = ''

        picking_obj = self.env['stock.picking']
        sale_obj = self.env['sale.order']
        seq_obj = self.env['ir.sequence']
        seq_ids = seq_obj.search([('code','=','sale.order')])

        sale_suffix = ''
        sale_prefix = ''
        if seq_ids:
            sale_suffix = seq_ids[0].suffix or ''
            sale_prefix = seq_ids[0].prefix or ''


        picking_ids = picking_obj.search([('state', '=', 'done'),('picking_type_id.code', '=', 'outgoing'), \
            ('write_date', '>=', start_date),('write_date', '<=', end_date),('partner_id.parent_id', '<=', partner.id)])

        #FILE HEADER
        #current_date = datetime.now()
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        #CONVERT DATE TO USER TZ
        #"%y%m%d%H%M%S"
        date = self.convert_tz(date, format="%Y-%m-%d %H:%M:%S")
        date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%y%m%d%H%M%S")
        
        data = data + self.format_element(size=50)
        data = data + date
        data = data + self.format_element(size=18)
        data = data + '\n'

        for picking in picking_ids:
            #print '......................'
            picking_prefix = picking.picking_type_id.sequence_id.prefix or ''
            picking_suffix = picking.picking_type_id.sequence_id.suffix or ''
            picking_name = picking.name
            picking_name = picking_name.replace(picking_prefix,'')
            picking_name = picking_name.replace(picking_suffix,'')

            delivery_suffix = picking.partner_id.name[0:2].upper()
            
            sale_ids = sale_obj.search([('procurement_group_id','=',picking.group_id.id)])
            if not sale_ids:
                raise ValidationError(_('Picking does not have a SO, ref: '+picking.name))
            # sale_name = sale_ids[0].name
            # sale_name = sale_name.replace(sale_suffix,'')
            # sale_name = sale_name.replace(sale_prefix,'')

            client_order_ref = sale_ids[0].client_order_ref
            if client_order_ref == False:
                client_order_ref = '     '
            
            #ENSAMBLE STRING
            #PICKING HEADER
            data = data + '4270101'
            data = data + self.format_element(size=15,element=picking_name,filler='0',f_side=False)

            #write_date = datetime.strptime(picking.write_date, "%Y-%m-%d %H:%M:%S").strftime('%y%m%d')
            #write_date = datetime.strptime(picking.write_date, "%Y-%m-%d %H:%M:%S")
            write_date = self.convert_tz(picking.write_date, format="%Y-%m-%d %H:%M:%S")
            write_date = datetime.strptime(write_date, "%Y-%m-%d %H:%M:%S").strftime('%y%m%d')
            data = data + write_date
            data = data + 'T'
            data = data + self.format_element(size=5,element=client_order_ref,filler=' ',f_side=False)
            data = data + delivery_suffix
            data = data + self.format_element(size=44)
            data = data + '\n'

            #LINES
            line_n = 1
            for move in picking.move_lines:
                if line_n > 2:
                    break
                data = data + '4270105'
                data = data + self.format_element(size=5,element=client_order_ref,filler='0',f_side=False)
                data = data + delivery_suffix
                data = data + '01'
                data = data + self.format_element(size=4,element=line_n,f_side=False,filler='0') + '0'
                #data = data + '00001'#no paquete
                data = data + self.format_element(size=5,element=move.product_id.manufacturer_product_ref,filler='0',f_side=False)
                #data = data + 'A'#A = AUTOS, M=MOTOS, P=PRODUCTOS DE FUERZA
                data = data + self.format_element(size=1,element=move.product_id.manufacturer_product_type)
                if not move.product_id.manufacturer_product_name:
                    raise ValidationError(_('Product does not have manufacturer product name defined: '+move.product_id.name))
                data = data + self.format_element(size=13,element=move.product_id.manufacturer_product_name)
                data = data + self.format_element(size=5,\
                    element=int(abs(move.product_uom_qty*move.product_id.manufacturer_product_ref)),filler='0',f_side=False)
                #data = data + self.format_element(size=7,element=move.product_id.lst_price,filler='0',f_side=False)
                # if move.product_uom_qty > 0:
                #     price = int(move.amount_stock_move/move.product_uom_qty)
                # else:
                price = int(move.product_id.lst_price)
                price = abs(price)
                #print 'move.amount_stock_move: ',move.amount_stock_move
                #print 'move.product_uom_qty: ',move.product_uom_qty
                #print 'price: ',price
                data = data + self.format_element(size=7,element=price,filler='0',f_side=False)

                data = data + self.format_element(size=28)
                data = data + '\n'

                line_n += 1

            # if line_n == 2:
            #     data = data + self.format_element(size=80)

        #SETTING UP FILE
        #data = base64.b64encode(data)
        #print 'data: \n',data
        datas_fname = 'ASN.txt'
        self.write({'cadena_decoding':"",
            'datas_fname':datas_fname,
            'file':base64.encodestring(data),
            #'file':data,
            'download_file': True})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.asn.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            }
        