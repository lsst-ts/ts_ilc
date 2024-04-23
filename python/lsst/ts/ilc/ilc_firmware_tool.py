#!/usr/bin/env python3

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
from typing import IO

from intelhex import IntelHex


def diff(diffhex: IntelHex, memhex: IntelHex) -> None:
    for s in diffhex.segments():
        for i in range(s[0], s[1]):
            if diffhex[i] != memhex[i] and i in memhex.addresses():
                print(f"Diff: {i:04x} {diffhex[i]:02x} {memhex[i]:02x}")


def hex_format(segments: list[tuple[int, int]]) -> str:
    return ", ".join([f"{s[0]:04x} - {s[1]:04x}" for s in segments])


def load_file(hex_file: IO, desc: str) -> IntelHex:
    ihex = IntelHex(hex_file)
    print(f"{desc} {hex_file.name}, segments {hex_format(ihex.segments())}")
    return ihex


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
    parser.add_argument("memdump", type=argparse.FileType("r"), help="Memory dump file")

    args = parser.parse_args()

    memhex = load_file(args.memdump, "Loaded ")

    if args.diff is not None:
        diffhex = load_file(args.diff, "Loaded original (diff) firmware ")
        diff(diffhex, memhex)
