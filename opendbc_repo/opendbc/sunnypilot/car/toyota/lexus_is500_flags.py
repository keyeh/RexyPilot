"""
Fork-local vehicle identity flag, kept out of ToyotaFlagsSP in values.py so that
submodule updates from upstream sunnypilot never touch or conflict with this file.

The bit is chosen far away from ToyotaFlagsSP's sequential allocation (currently
1, 2, 4, 8, 16) to avoid silently colliding with a future upstream flag that reuses
the "next" value.
"""

import re

from opendbc.car import structs

LEXUS_IS500 = 1 << 30

# Lexus IS500 VIN pattern from the "IS500 Specifications Datasheet" on ClubLexus
# https://docs.google.com/spreadsheets/d/1XRBDXN2yp0V7N5q0xV44DhZoU8xgInP0la2SlUfflzc
LEXUS_IS500_VIN_RE = re.compile(r'^JTH.P1D2..500....$')


def is_lexus_is500(CP_SP: structs.CarParamsSP) -> bool:
  return bool(CP_SP.flags & LEXUS_IS500)
