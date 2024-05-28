# Diff two Intel hex files.
#
# Developed for the LSST Telescope and Site.
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

import argparse

from intelhex import IntelHex

from .ilc_hex import ILCHex


def diff(diffhex: IntelHex, memhex: IntelHex) -> None:
    """Differentiate two hex dumps. Only addresses from the first provided file
    are checked.

    Parameters
    ----------
    diffhex : `IntelHex`
        Intel hex file to differentiate. It's addresses are used for diff.
    memhex : `IntelHex`
        This shall be full MCU flash memory dump.
    """
    for s in diffhex.segments():
        if not (memhex.has_range(s[0], s[1] - s[0])):
            print(f"Diff: range not fully loaded: 0x{s[0]:06x} - 0x{s[1]:06x}")
        for i in range(s[0], s[1]):
            if diffhex[i] != memhex[i]:
                print(f"Diff: {i:06x} {diffhex[i]:02x} {memhex[i]:02x}")


def run() -> None:
    parser = argparse.ArgumentParser(
        description="Tool to work with the Intel Hex memory dumps and "
        "firmware files."
    )
    parser.add_argument(
        "-d",
        dest="diff",
        type=argparse.FileType("r"),
        help="Diff against this firmware file",
    )
    parser.add_argument(
        "-i",
        action="store_true",
        dest="ivt",
        default=False,
        help="Print J-IVT table contents",
    )
    parser.add_argument("memdump", type=argparse.FileType("r"), help="Memory dump file")

    args = parser.parse_args()

    memhex = ILCHex(args.memdump, "Loaded ")

    try:
        memhex.verify()
    except ILCHex.NotInRangeError as er:
        print("This isn't a hex dump: " + str(er))

    if args.ivt is True:
        # address 0x1600 (in words - 2 bytes) = 0x2c00 (in bytes). Comes from
        # ILC linkmap files
        memhex.print_ivt(0x1600)

    if args.diff is not None:
        diffhex = ILCHex(args.diff, "Loaded original (diff) firmware ")
        diff(diffhex, memhex)
