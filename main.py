"""
CHIP-8 Interpreter, implemented in python, via pyqt6.
"""

from PyQt6.QtWidgets import QApplication, QMainWindow
import pprint

font = bytes([0xF0, 0x90, 0x90, 0x90, 0xF0,
              0x20, 0x60, 0x20, 0x20, 0x70,
              0xF0, 0x10, 0xF0, 0x80, 0xF0,
              0xF0, 0x10, 0xF0, 0x10, 0xF0,
              0x90, 0x90, 0xF0, 0x10, 0x10,
              0xF0, 0x80, 0xF0, 0x10, 0xF0,
              0xF0, 0x80, 0xF0, 0x90, 0xF0,
              0xF0, 0x10, 0x20, 0x40, 0x40,
              0xF0, 0x90, 0xF0, 0x90, 0xF0,
              0xF0, 0x90, 0xF0, 0x10, 0xF0,
              0xF0, 0x90, 0xF0, 0x90, 0x90,
              0xE0, 0x90, 0xE0, 0x90, 0xE0,
              0xF0, 0x80, 0x80, 0x80, 0xF0,
              0xE0, 0x90, 0x90, 0x90, 0xE0,
              0xF0, 0x80, 0xF0, 0x80, 0xF0,
              0xF0, 0x80, 0xF0, 0x80, 0x80
              ])
RAM = bytearray(4096)
"""4kB of 'RAM'"""

PC = bytearray(2)
"""12 bit address pointing to current instruction in memory. Actually 16 bits, but never uses more than 12."""

INDEX_REGISTER = bytearray(2)
"""12 bit index register. Actually 16 bits, but never uses more than 12."""

SUBROUTINE_STACK = []
"""Stack that holds 16 bit addresses pointing to subroutines(functions)"""

DELAY_TIMER = 0
"""An 8-bit delay timer which is decremented at a rate of 60 Hz (60 times per second) until it reaches 0"""

SOUND_TIMER = 0
"""An 8-bit sound timer which functions like the delay timer, but which also gives off a beeping sound as long as it’s not 0"""

REGISTERS = bytearray(16)
"""16 8-bit gen purpose registers. VF used for flags."""

if __name__ == '__main__':
    print(f'RAM: {RAM}')
    print(f'PC: {PC}')
    print(f'I: {INDEX_REGISTER}')
    print(f'Registers: {REGISTERS}')