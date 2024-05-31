# This file is part of ts_ilc.
#
# Developed for the Rubin Observatory Telescope and Site System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import pathlib
import unittest

from lsst.ts.ilc import ILCHex


class ILCHexTestCase(unittest.TestCase):
    def test_loading(self) -> None:
        ilchex = ILCHex(
            open(
                pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
                / "data"
                / "ilc.hex"
            ),
            "Loading test data ilc.hex",
        )
        self.assertEqual(ilchex.rd_latch(0x1600), 0x1BE6)
        self.assertEqual(ilchex.has_range(0x2BFF, 1), False)
        self.assertEqual(ilchex.has_range(0x2C00, 1), True)
        self.assertRaises(ILCHex.NotInRangeError, ilchex.verify)


if __name__ == "__main__":
    unittest.main()
