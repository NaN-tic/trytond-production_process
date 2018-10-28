# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import product
from . import production


def register():
    Pool.register(
        production.Process,
        production.Step,
        production.BOMInput,
        production.BOMOutput,
        production.Operation,
        production.Route,
        production.BOM,
        production.Production,
        product.ProductBom,
        production.StockMove,
        module='production_process', type_='model')
