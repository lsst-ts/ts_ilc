# Simplify access to ILC hex files
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


from typing import IO

import crcmod
from intelhex import IntelHex

modbus_crc_fun = crcmod.predefined.mkCrcFun("modbus")


def hex_format(segments: list[tuple[int, int]]) -> str:
    """Returns address range in string.

    Paramaters
    ----------
    segments : `list[tuple[int, int]]`
        Segments as returned by IntelHex.segments() function

    Returns
    -------
        Formatted string with hex segments range, joined with ,
    """
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

    class NotInRangeError(RuntimeError):
        """
        Raised when address is outside ILC range.

        Parameters
        ----------
        start : int`
            Starting address.
        end : `int`
            End address.
        msg : `str`, optional
            Optional message to add before error description.
        """

        def __init__(self, start: int, end: int, msg: str = ""):
            if msg == "":
                super().__init__(
                    f"Address range {start} - {end} "
                    f"(0x{start:06x} - 0x{end:06x}) "
                    "is outside loaded range."
                )
            else:
                super().__init__(
                    f"{msg}: address range {start} - {end} "
                    f"(0x{start:06x} - 0x{end:06x}) "
                    "is outside loaded range."
                )

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
            raise self.NotInRangeError(start, start + length)

        # substract 1 from length as tobinarray returns data including the byte
        # at the end address
        return modbus_crc_fun(self.tobinarray(start, start + length - 1))

    def verify(self) -> bool:
        """
        Assumes the hex file contains whole MPU dump, print various interesting
        addresses and verify both application statistics CRC and application
        CRC. Prints results to standard output.

        Returns
        -------
        verified : `bool`
            True if loaded hex code CRCs matches.
        """
        verified = True
        if not (self.has_range(self.STAT_ADDR_START, 16)):
            raise self.NotInRangeError(
                self.STAT_ADDR_START,
                self.STAT_ADDR_START + 16,
                "Cannot retrieve application statistics record",
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
            raise self.NotInRangeError(
                application_start,
                application_start + application_length,
                "Cannot retrieve content of the application programme",
            )
        app_crc = self.rd_latch(self.STAT_ADDR_APP_CRC)
        cal_app_crc = self.ilc_crc(application_start, application_length)
        print(f"Application CRC {app_crc:04x}")
        print(f"Calculated Application CRC {cal_app_crc:04x}")
        if app_crc != cal_app_crc:
            verified = False
            print("Application CRC doesn't match!")

        return verified

    def print_ivt(self, base: int) -> None:
        """
        Print the Interrupt Vector Table (IVT) content, including description
        taken from the linkmap.

        Parameters
        ----------
        base : `int`
            Base address of the memory holding the IVT.
        """
        __addresses = [
            "Reserved Trap 0",
            "Oscillator Fail",
            "Address Error",
            "Stack Error",
            "Math Error",
            "Reserved Trap 5",
            "Reserved Trap 6",
            "Reserved Trap 7",
            "INT0 Interrupt",
            "IC1 Interrupt",
            "OC1 Interrupt",
            "T1 Interrupt",
            "Interrupt 4",
            "IC2 Interrupt",
            "OC2 Interrupt",
            "T2 Interrupt",
            "T3 Interrupt",
            "SPI1 Error Interrupt",
            "SPI1 Interrupt",
            "U1RX Interrupt",
            "U1 TX Interrupt",
            "ADC1 Interrupt",
            "Interrupt 14",
            "Interrupt 15",
            "SI2 C1 Interrupt",
            "MI2 C1 Interrupt",
            "Comp Interrupt",
            "CN Interrupt",
            "INT1 Interrupt",
            "Interrupt 21",
            "Interrupt 22",
            "Interrupt 23",
            "Interrupt 24",
            "OC3 Interrupt",
            "Interrupt 26",
            "T4 Interrupt",
            "T5 Interrupt",
            "INT2 Interrupt",
            "U2RX Interrupt",
            "U2TX Interrupt",
            "SPI2 Error Interrupt",
            "SPI2 Interrupt",
            "Interrupt 34",
            "Interrupt 35",
            "Interrupt 36",
            "IC3 Interrupt",
            "Interrupt 38",
            "Interrupt 39",
            "Interrupt 40",
            "Interrupt 41",
            "Interrupt 42",
            "Interrupt 43",
            "Interrupt 44",
            "Interrupt 45",
            "Interrupt 46",
            "Interrupt 47",
            "Interrupt 48",
            "SI2 C2 Interrupt",
            "MI2 C2 Interrupt",
            "Interrupt 51",
            "Interrupt 52",
            "Interrupt 53",
            "Interrupt 54",
            "Interrupt 55",
            "Interrupt 56",
            "Interrupt 57",
            "Interrupt 58",
            "Interrupt 59",
            "Interrupt 60",
            "Interrupt 61",
            "RTC Interrupt",
            "Interrupt 63",
            "Interrupt 64",
            "U1 Error Interrupt",
            "U2 Error Interrupt",
            "CRC Interrupt",
            "Interrupt 68",
            "Interrupt 69",
            "Interrupt 70",
            "Interrupt 71",
            "LVD Interrupt",
            "Interrupt 73",
            "Interrupt 74",
            "Interrupt 75",
            "Interrupt 76",
            "Interrupt 77",
            "Interrupt 78",
            "Interrupt 79",
            "ULPWU Interrupt",
            "Interrupt 81",
            "Interrupt 82",
            "Interrupt 83",
            "Interrupt 84",
            "Interrupt 85",
            "Interrupt 86",
            "Interrupt 87",
            "Interrupt 88",
            "Interrupt 89",
            "Interrupt 90",
            "Interrupt 91",
            "Interrupt 92",
            "Interrupt 93",
            "Interrupt 94",
            "Interrupt 95",
            "Interrupt 96",
            "Interrupt 97",
            "Interrupt 98",
            "Interrupt 99",
            "Interrupt 100",
            "Interrupt 101",
            "Interrupt 102",
            "Interrupt 103",
            "Interrupt 104",
            "Interrupt 105",
            "Interrupt 106",
            "Interrupt 107",
            "Interrupt 108",
            "Interrupt 109",
            "Interrupt 110",
            "Interrupt 111",
            "Interrupt 112",
            "Interrupt 113",
            "Interrupt 114",
            "Interrupt 115",
            "Interrupt 116",
            "Interrupt 117",
        ]

        for interrupt in __addresses:
            lb = self.rd_latch(base)
            jump = self.rd_latch(base + 1)
            ub = self.rd_latch(base + 2)
            zero = self.rd_latch(base + 3)

            if jump != 0x04 or zero != 0:
                print(f"Invalid hex entry - jump: {jump:04x} zero: {zero:04x}")
            print(f"{interrupt:>22}: {ub:04x} {lb:04x}")

            base += 4
