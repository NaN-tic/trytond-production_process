# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .product import *
from .production import *


def register():
    Pool.register(
        Process,
        Step,
        BOMInput,
        BOMOutput,
        Operation,
        Route,
        BOM,
        Production,
        Product,
        ProductBom,
        module='production_process', type_='model')
