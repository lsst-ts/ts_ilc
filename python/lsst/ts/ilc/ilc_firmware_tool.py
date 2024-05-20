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

import crcmod
from intelhex import IntelHex

modbus_crc_fun = crcmod.predefined.mkCrcFun("modbus")


def hex_format(segments: list[tuple[int, int]]) -> str:
    return ", ".join([f"{s[0]:04x} - {s[1]:04x}" for s in segments])


class ILCHex(IntelHex):
    """Provides functions to manipulate ILC hex file. Constants are taken from
    C ILC source code."""

    SYS_STATUS_ADDR = 0x0F00  # Addr of system status word
    SYS_FLAGS_ADDR = 0x0F02  # Addr of system flags word
    MB_FLAGS_ADDR = 0x0F04  # Addr of MODBUS flags word
    SYS_FAULT_ADDR = 0x0F06  # Addr of system fault word
    RESET_CMD_ADDR = 0x0F08  # Addr of reset command
    MBFUNC_ADDR = 0x0F0A  # Addr of last mb function before reset
    EVENT_ADDR = 0x0F0C  # Addr of event code
    MB_DIAGCTR_ADDR = 0x0F10  # Addr of mbserial_diag_counter(s)

    ADDR_DEFAULT = 0x000000  # default (failed address)
    CODE_ADDR_MAX = 0x0057FE  # End of usable code space
    CODE_ADDR_LAST_PAGE = (
        0x0057C0  # Start address of last application page that can be programmed
    )

    APP_ADDR_MIN = 0x001600  # Beginning of user code space
    APP_ADDR_START_VECTOR = 0x001800  # User app reset vector location
    APP_ADDR_START = 0x001810  # User app default start address
    APP_ADDR_LAST_PAGE = (
        0x005780  # Start address of last application page that can be programmed
    )
    BL_ADDR_START = 0x000200  # Start of BL protection code
    BL_ADDR_END = 0x0015FE  # End of BL protection area

    APP_MAX_LEN = CODE_ADDR_MAX - APP_ADDR_MIN + 2  # Max length of app firmware
    APP_MAX_PAGE_LEN = APP_MAX_LEN / 64  # Instrn pages of firmware

    # The stats addresses below must be contiguous. The stat length below must
    # be length in instruction size (excluding the stat crc value).  Statistics
    # include crc16 value, start addr of code, end address of program.  These
    # are used by the application for integrity checks.
    STAT_ADDR_START = 0x0057C0  # App program stats start

    STAT_ADDR_APP_CRC = 0x0057C0  # CRC16 value for app start to end
    STAT_ADDR_APP_START = 0x0057C2  # start address for CRC16 calc
    STAT_ADDR_APP_LEN = 0x0057C4  # Length of app code for CRC16 calc
    STAT_ADDR_STAT_CRC = 0x0057C6  # CRC16 value app stats

    STAT_LEN = 3  # Instruction length of application stat data (used for crc check) ...

    def __init__(self, hex_file: IO, desc: str):
        super().__init__(hex_file)
        print(f"{desc} {hex_file.name}, segments {hex_format(self.segments())}")

    def has_range(self, start: int, length: int) -> bool:
        """Confirms address range is among addresses explicitly loaded from the
        hex file (e.g. is in segments).

        Parameters
        ----------
        start : `int`
            Range start address (in 8 bit addressing).
        length: `int`
            Range length (in 8 bits / bytes).

        Returns
        -------
            True if the whole address range was loaded from the hex file.
        """
        for s in self.segments():
            if s[0] <= start and start < s[1]:
                a = start + length
                if a > s[1]:
                    return False
                return True
        return False

    def rd_latch(self, addr: int) -> int:
        """Read FLASH. The name originates from ILC C method.

        Parameters
        ----------
        addr : `int`
            Address to load in 16-bits addressing.

        Returns
        -------
        data : `int`
            16 bit (2 bytes) integer, representing data (using proper endian)
            at supplied address.
        """
        add = addr << 1
        return self[add] + (self[add + 1] << 8)

    def ilc_crc(self, start: int, length: int) -> int:
        """Returns CRC16(Modbus) CRC calculated from given address range.

        Parameters
        ----------
        start : `int`
            Range start address (in 8 bit addressing).
        length: `int`
            Range length (in 8 bits / bytes).

        Returns
        -------
        crc : `int`
            CRC calculated from start address to start + length byte. This
            should be directly (with correct endianness) comparable to any
            value read with rd_latch.
        """
        if not (self.has_range(start, length)):
            raise RuntimeError(
                f"Address range {start} - {start + length} "
                f"(0x{start:06x} - 0x{start + length:06x}) "
                "is outside loaded range."
            )

        # substract 1 from length as tobinarray returns data including the byte
        # at the end address
        return modbus_crc_fun(self.tobinarray(start, start + length - 1))

    def verify(self) -> bool:
        """Assumes the hex file contains whole MPU dump, print various
        interesting addresses and verify both application statistics CRC and
        application CRC. Prints results to standard output.

        Returns
        -------
        verified : `bool`
            True if loaded hex code CRCs matches.
        """
        verified = True
        if not (self.has_range(self.STAT_ADDR_START, 16)):
            raise RuntimeError(
                "Application statistics addresses "
                f"(0x{self.STAT_ADDR_START:06x} - 0x{self.STAT_ADDR_START + 16:06x}) not loaded."
            )
        print(f"Reset command address {self.rd_latch(self.RESET_CMD_ADDR):04x}")
        application_start = self.rd_latch(self.STAT_ADDR_APP_START)
        print(f"Application start address {application_start:04x}")
        application_length = self.rd_latch(self.STAT_ADDR_APP_LEN)
        print(f"Application length {application_length}")
        print(f"Application end {(application_start + application_length):04x}")
        stat_crc = self.rd_latch(self.STAT_ADDR_STAT_CRC)
        cal_stat_crc = self.ilc_crc(self.STAT_ADDR_START << 1, 12)
        print(f"Stat CRC {stat_crc:04x}")
        print(f"Calculated Stat CRC {cal_stat_crc:04x}")
        if stat_crc != cal_stat_crc:
            verified = False
            print("Application statistics CRC doesn't match!")

        if not (self.has_range(application_start, application_length)):
            raise RuntimeError(
                "Application programme on addresses "
                f"0x{application_start:06x} - 0x{application_start + application_length:06x} "
                "not fully loaded."
            )
        app_crc = self.rd_latch(self.STAT_ADDR_APP_CRC)
        cal_app_crc = self.ilc_crc(application_start, application_length)
        print(f"Application CRC {app_crc:04x}")
        print(f"Calculated Application CRC {cal_app_crc:04x}")
        if app_crc != cal_app_crc:
            verified = False
            print("Application CRC doesn't match!")

        return verified


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
    parser.add_argument("memdump", type=argparse.FileType("r"), help="Memory dump file")

    args = parser.parse_args()

    memhex = ILCHex(args.memdump, "Loaded ")
    memhex.verify()

    if args.diff is not None:
        diffhex = ILCHex(args.diff, "Loaded original (diff) firmware ")
        diff(diffhex, memhex)
