# Adapted from openpyxl 3.1.5 (MIT, Copyright (c) 2010 openpyxl); see third_party/licenses/openpyxl-MIT.txt.

"""
math.prod equivalent for < Python 3.8
"""

import functools
import operator


def product(sequence):
    return functools.reduce(operator.mul, sequence)


try:
    from math import prod
except ImportError:
    prod = product
