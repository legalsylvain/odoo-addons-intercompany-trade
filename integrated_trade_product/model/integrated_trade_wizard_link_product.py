# -*- encoding: utf-8 -*-
##############################################################################
#
#    Integrated Trade - Product module for OpenERP
#    Copyright (C) 2014-Today GRAP (http://www.grap.coop)
#    @author Sylvain LE GAL (https://twitter.com/legalsylvain)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import SUPERUSER_ID
from openerp.osv import fields
from openerp.osv.orm import TransientModel
from openerp.osv.osv import except_osv
from openerp.tools.translate import _
from openerp.addons import decimal_precision as dp

from .custom_tools import _compute_integrated_prices


class integrated_trade_wizard_link_product(TransientModel):
    _name = 'integrated.trade.wizard.link.product'

    # Default Get Section
    def default_get(self, cr, uid, fields, context=None):
        pp_obj = self.pool['product.product']
        pitc_obj = self.pool['product.integrated.trade.catalog']
        rit_obj = self.pool['res.integrated.trade']
        res = super(integrated_trade_wizard_link_product, self).default_get(
            cr, uid, fields, context=context)
        supplier_product_id = pitc_obj._get_supplier_product_id_from_id(
            context.get('active_id'))
        integrated_trade_id = pitc_obj._get_integrated_trade_id_from_id(
            context.get('active_id'))
        rit = rit_obj.browse(
            cr, SUPERUSER_ID, integrated_trade_id, context=context)
        supplier_pp = pp_obj.browse(
            cr, SUPERUSER_ID, supplier_product_id, context=context)
        price_info = _compute_integrated_prices(
            self.pool, cr, SUPERUSER_ID, supplier_pp,
            rit.supplier_partner_id, rit.pricelist_id, customer_product=False,
            context=context)
        res.update({
            'supplier_product_id': supplier_product_id,
            'integrated_trade_id': integrated_trade_id,
            'supplier_product_name': supplier_pp.name,
            'supplier_product_code': supplier_pp.default_code,
            'supplier_sale_price_vat_excl': (
                price_info['supplier_sale_price_vat_excl']),
            'supplier_sale_price_vat_incl': (
                price_info['supplier_sale_price_vat_incl']),
        })
        return res

    # Column Section
    _columns = {
        'integrated_trade_id': fields.many2one(
            'res.integrated.trade', 'Integrated Trade',
            required=True, readonly=True),
        'customer_product_id': fields.many2one(
            'product.product', 'Customer Product', required=True),
        'customer_product_tmpl_id': fields.related(
            'customer_product_id', 'product_tmpl_id', type='many2one',
            relation='product.template', string='Customer Template',
            readonly=True),
        'supplier_product_id': fields.many2one(
            'product.product', 'Supplier Product',
            required=True, readonly=True),
        # The Following Field are used to display external information
        # And avoir ACL problem
        'supplier_product_code': fields.char(
            'Supplier Product Code', readonly=True),
        'supplier_product_name': fields.char(
            'Supplier Product Name', readonly=True),
        'supplier_sale_price_vat_excl': fields.float(
            'Supplier Sale Price VAT Excluded', readonly=True,
            digits_compute=dp.get_precision('Integrated Product Price')),
        'supplier_sale_price_vat_incl': fields.float(
            'Supplier Sale Price VAT Included', readonly=True,
            digits_compute=dp.get_precision('Integrated Product Price')),
    }

    # Button Section
    def link_product(self, cr, uid, ids, context=None):
        psi_obj = self.pool['product.supplierinfo']
        pt_obj = self.pool['product.template']
        pp_obj = self.pool['product.product']
        pitc_obj = self.pool['product.integrated.trade.catalog']
        for itwlp in self.browse(cr, uid, ids, context=context):
            # Prepare Product Supplierinfo
            psi_vals = psi_obj._integrated_trade_prepare(
                cr, uid, itwlp.integrated_trade_id.id,
                itwlp.supplier_product_id.id,
                itwlp.customer_product_id.id, context=context)
            psi_vals['product_id'] = itwlp.customer_product_tmpl_id.id

            cus_pt = pt_obj.browse(
                cr, uid, psi_vals['product_id'], context=context)
            sup_pp = pp_obj.browse(
                cr, SUPERUSER_ID, psi_vals['supplier_product_id'],
                context=context)

            # Raise error if there is many products associated to the template
            pp_qty = pp_obj.search(cr, uid, [
                ('product_tmpl_id', '=', itwlp.customer_product_tmpl_id.id),
            ], context=context)
            if len(pp_qty) != 1:
                raise except_osv(
                    _("Too Many Products for the Template!"),
                    _(
                        """You can not link this Template %s because there"""
                        """ are %d Products associated.""") % (
                        cus_pt.name, len(pp_qty)))

            # raise error if there is a product linked
            pitc_ids = pitc_obj.search(cr, uid, [
                ('customer_product_tmpl_id', '=', psi_vals['product_id']),
                ('customer_company_id', '=', psi_vals['company_id']),
            ], context=context)
            if len(pitc_ids) != 0:
                raise except_osv(
                    _("Duplicated Reference!"),
                    _(
                        """You can not link the Product Template %s because"""
                        """ it is yet linked to another supplier product."""
                        """ Please unlink the Product Template and try"""
                        """ again.""") % (cus_pt.name))

            # Raise an error if Unit doesn't match
            if cus_pt.uom_id.category_id.id != sup_pp.uom_id.category_id.id:
                raise except_osv(
                    _("Unit Mismatch!"),
                    _(
                        """The type of Unit of Mesure of your product"""
                        """ is '%s'.\nThe type of Unit of Mesure of the"""
                        """ supplier product is '%s'.\n\nThe type must"""
                        """ be the same.""") % (
                            cus_pt.uom_id.category_id.name,
                            sup_pp.uom_id.category_id.name))

            psi_obj.create(cr, uid, psi_vals, context=context)
        return True
