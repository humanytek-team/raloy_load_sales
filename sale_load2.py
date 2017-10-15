# -*- encoding: utf-8 -*-
from openerp import api, fields, models, _
from openerp.exceptions import UserError, RedirectWarning, ValidationError
import base64

class SaleLoadWizard2(models.TransientModel):
    _name = 'sale.load.wizard2'


    partner_id = fields.Many2one('res.partner', 'Partner', domain="[('edi_load', '=', True)]", required=True)
    txt_file = fields.Binary(string='Archivo (*.txt)',
                    filters='*.txt', 
                    help='Seleccione el archivo a cargar (*.txt)', required=True)


    def get_source(self):
        source = False
        res = self.env['utm.source'].search([('name', '=', 'Edi Local')])
        if len(res) > 0:
            source = res[0]
            return source.id
        return False

    def search_partner_delivery(self,letters):
        """
        searches contact which name beggins with the letters in 'letters'
        from Idemitsu / Honda
        """
        #print '-------------------'
        #print 'letters: ',letters
        #print 'self.partner_id: ',self.partner_id.name
        company_id = self.env.user.company_id.id

        parent_id = self.partner_id.id
        letters_low = letters.lower() + '%%'
        self.env.cr.execute(
            """
            SELECT id FROM res_partner WHERE company_id = %s AND parent_id = %s AND active = True AND LOWER(name) LIKE %s
            """,
            (company_id,parent_id,letters_low)
        )
        res = self.env.cr.dictfetchall()
        #print '-------------------'
        if len(res) > 0:
            #return res[0]['id']
            return self.env['res.partner'].search([('id', '=', res[0]['id'])])
        else:
            raise ValidationError(_('Partner not found, ref: '+letters))


    def search_product(self,ref):
        product = False
        #print '??'+ref+'??'
        pp = self.env['product.product']
        #pp = self.env['product.template']
        #res = pp.search([('default_code', '=', ref)])
        #res = pp.search([('barcode', '=', ref)])
        res = pp.search([('manufacturer_product_name', '=', ref)])
        #manufacturer_product_name
        #manufacturer_product_ref
        if len(res) > 0:
            product = res[0]

        if product == False:
            raise ValidationError(_('Product not found, ref: '+ref))

        return product


    def action_load(self):
        """
        reads file and loads sale orders
        """
        partner = self.partner_id
        so = self.env['sale.order']
        afp = self.env['account.fiscal.position']
        so_fields = [] #WILL CONTAIN FIELDS FOR SALE ORDER, EACH ELEMENT IS A SALE ORDER
        order_lines = []
        fields = {}
        source = self.get_source()
        file_txt = base64.decodestring(self.txt_file)
        line_n = 1 #LINE NUMBER

        for line in file_txt.splitlines():

            if line_n == 1: #HEADER
                #MOST OF THESE ARE NOT USED, BUT ARE KEPT FOR FUTURE REFERENCE
                XHID = line[0:2] #ID de Registro
                XHINTF = line[2:4] #Interfaz                                                               
                XHSBS1 = line[4:6] #Subsidiaria                          
                XHNSEQ = line[6:8] #Secuencia                            
                XHTREG = line[8:13] #Total de Registros                    
                XHTTRN = line[13:14] #Tipo de Transmisión                  
                XHSBS2 = line[14:16] #Subsidiaria                          
                XHFL34 = line[16:50] #Filler                               
                XHFTRN = line[50:56] #Fecha de Transmisión                 
                XHHTRN = line[56:62] #Hora de Transmisión                  
                XHFL18 = line[62:80] #Filler                               
            else:
                #MOST OF THESE ARE NOT USED, BUT ARE KEPT FOR FUTURE REFERENCE
                XLSBS1 = line[0:2] #Subsidiaria                                       
                XLCODD = line[2:4] #Código de Datos                                   
                XLSBS2 = line[4:6] #Subsidiaria                                       
                XLCODR = line[6:7] #Código de Registro                                
                XLORDN = line[7:12] #Orden de Compra                                   
                XLSUFJ = line[12:14] #Sufijo                                            
                XLINST = line[14:16] #Instrucciones de Envío 

                XLLIN1 = line[16:21] #Número de Línea                                   
                XLCOD1 = line[21:34] #Código de Artículo                                
                XLCAN1 = line[34:39] #Cantidad                                          
                XLFL9A = line[39:48] #Filler                                            

                XLLIN2 = line[48:53] #Número de Línea                                   
                XLCOD2 = line[53:66] #Código de Artículo                                
                XLCAN2 = line[66:71] #Cantidad                                          
                XLFL9B = line[71:80] #Filler

                partner_delivery = self.search_partner_delivery(XLSUFJ)
                #print 'partner_delivery: ',partner_delivery
                fiscal_position_id = afp.get_fiscal_position(partner.id, partner_delivery.id)

                fields = {
                    'name':XLORDN,
                    'partner_id':partner.id,
                    'partner_shipping_id': partner_delivery.id,
                    'fiscal_position_id':fiscal_position_id,
                    'pricelist_id': partner.property_product_pricelist and partner.property_product_pricelist.id or False,
                    'payment_term_id': partner.property_payment_term_id and partner.property_payment_term_id.id or False,
                    'pay_method_id': partner.pay_method_id and partner.pay_method_id.id or False,
                    'source_id': source,
                }

                order_lines = []
                if XLCOD1.replace(" ", "") != '':
                    
                    product1 = self.search_product(XLCOD1)
                    qty1 = 0.0
                    if product1.manufacturer_product_ref > 0:
                        qty1 = int(XLCAN1) / product1.manufacturer_product_ref

                        line_fields = {
                            'product_id':product1.id,
                            'product_uom_qty':qty1,
                        }

                        order_lines.append((0,0,line_fields))
                    else:
                        raise ValidationError(_('Edi package not set for product '+product.name))

                #print 'XLCOD2: ',XLCOD2
                if XLCOD2.replace(" ", "") != '':
                    product2 = self.search_product(XLCOD2)
                    if product2.manufacturer_product_ref > 0:
                        qty2 = int(XLCAN2) / product2.manufacturer_product_ref

                        line_fields2 = {
                            'product_id':product2.id,
                            'product_uom_qty':qty2,
                        }

                        order_lines.append((0,0,line_fields2))
                    else:
                        raise ValidationError(_('Edi package not set for product '+product2.name))


                fields['order_line'] = order_lines
                so_fields.append(fields)


            line_n += 1

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