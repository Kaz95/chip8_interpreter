"""
CHIP-8 Interpreter, implemented in python, via pyqt6.

TODO:
    * Implement the rest of the Opcodes
    * Add Step feature as debugging measure.
    * Add memory viewer that allows editing to aid debugging.
    * Implement Load font function
    * Make all the global vars class attributes unless I find display needs to access them directly.
    * Write tests

"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtCore import QThread
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem

from enum import IntEnum


class OpcodeCategory(IntEnum):
    FLOW_AND_SYSTEM = 0x0
    JUMP = 0x1
    SET_CONSTANT = 0X6
    ADD_CONSTANT = 0X7
    MEMORY_INDEX = 0XA
    DRAW = 0XD


class OpCodes(IntEnum):
    CLEAR_SCREEN = 0x00E0
    RETURN = 0x00EE


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

# PC = bytearray(2)
# """12 bit address pointing to current instruction in memory. Actually 16 bits, but never uses more than 12."""

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


class EmulatedDisplay(QGraphicsView):
    """Subclass and extend QGraphicsView to serve as emulated display output."""

    pause_toggle_signal = pyqtSignal(bool)

    def __init__(self, scale_factor=10):
        super().__init__()
        self.px_width = 64
        self.px_height = 32
        self.scale_factor = scale_factor
        self.bytes_buffer = bytearray(2048)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pixmap_item = QGraphicsPixmapItem()

        for row in range(self.px_height):
            row_offset = row * self.px_width

            if row == 0 or row == (self.px_height - 1):
                self.bytes_buffer[row_offset:row_offset + self.px_width] = b'\xff' * self.px_width
            else:
                # pass
                self.bytes_buffer[row_offset] = 255
                self.bytes_buffer[row_offset + self.px_width - 1] = 255

        self.image = QImage(self.bytes_buffer, self.px_width, self.px_height, self.px_width,
                            QImage.Format.Format_Grayscale8)
        self.scene = QGraphicsScene()
        self.pixmap_item.setPixmap(QPixmap.fromImage(self.image))
        self.scene.addItem(self.pixmap_item)
        self.setScene(self.scene)
        self.scale(self.scale_factor, self.scale_factor)
        self.setFixedSize(self.px_width * self.scale_factor, self.px_height * self.scale_factor)

    def update_screen(self, frame_buffer: list):
        self.bytes_buffer = bytearray([255 if x == 1 else 0 for x in frame_buffer])
        self.image = QImage(self.bytes_buffer, self.px_width, self.px_height, self.px_width,
                            QImage.Format.Format_Grayscale8)
        self.pixmap_item.setPixmap(QPixmap.fromImage(self.image))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_P:
            self.pause_toggle_signal.emit(True)


class EmulatedCPU(QThread):
    """Subclass and extend QThread to serve as emulated cpu."""
    render_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        RAM[0x200] = 0x6F
        RAM[0x201] = 0x05
        RAM[0x202] = 0x7F
        RAM[0x203] = 0x05
        RAM[0x204] = 0xAF
        RAM[0x205] = 0xFF
        self.PC = bytearray(2)
        self.PC[0] = 0x02
        self.paused = False
        self.running = True
        self.display_buffer = [0] * (64 * 32)

        # Timing constants
        self.clock_speed = 700
        self.frame_rate = 60
        self.cycles_per_frame = int(self.clock_speed / self.frame_rate)

    def run(self):
        import time
        frame_duration = 1.0 / self.frame_rate

        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue
            start_time = time.perf_counter()

            # Execute cycle burst for this frame
            for _ in range(self.cycles_per_frame):
                self.fetch_decode_execute()

            # Emit a copy of the buffer to the GUI thread
            self.render_signal.emit(self.display_buffer.copy())

            # Sleep to regulate frame rate
            elapsed = time.perf_counter() - start_time
            sleep_time = frame_duration - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def pause(self):
        if not self.paused:
            self.paused = True
        else:
            self.paused = False

    def stop(self):
        self.running = False

    def fetch_decode_execute(self):
        # Grab next two bytes, starting at PC. PC should start at 0x200.
        hi_byte = self.PC[0]
        lo_byte = self.PC[1]
        # Combine em using bit shifting and OR bitwise operator. This is the 16-bit address of the next instruction.
        next_instruction_address = hi_byte << 8 | lo_byte

        # Handle Jump that would cause PC to exceed RAM.
        if next_instruction_address + 1 > 0xFFF:
            print('PC out of range.')
            self.pause()
            return

        # Grab the2 bytes of the instruction and combine them in the same way.
        next_instruction = RAM[next_instruction_address] << 8 | RAM[next_instruction_address + 1]

        # Increment PC 2 bytes. Will be ready for next fetch.
        next_instruction_address += 2

        # Wrap if exceed ram buffer size. FIXME May add error here because afaik CHIP8 programs shouldn't ever cause a wrap.
        next_instruction_address = next_instruction_address & 0x0FFF

        # print(f'{next_instruction_address:#06X}')
        hi_byte = next_instruction_address >> 8
        lo_byte = next_instruction_address & 0x00FF

        self.PC[0] = hi_byte
        self.PC[1] = lo_byte
        # pprint.pp(self.PC.hex())

        # Mask off most significant nibble with &. Big Endian....think I have that right...most sig on right.
        next_instruction_cat = (next_instruction >> 12)
        # print(f'{next_instruction_cat:#06X}')

        second_nibble = (next_instruction & 0x0F00) >> 8
        third_nibble = (next_instruction & 0x00F0) >> 4
        fourth_nibble = next_instruction & 0x000F


        second_third_fourth_nibble = (second_nibble << 8 | third_nibble << 4 | fourth_nibble)
        third_fourth_nibble = (third_nibble << 4 | fourth_nibble)
        print(f'{next_instruction:#06X}')
        print(f'{second_third_fourth_nibble:#06X}')
        print(f'{third_fourth_nibble:#06X}')
        # print(second_nibble)
        print(f'{second_nibble:#06X}')
        # print(third_nibble)
        print(f'{third_nibble:#06X}')
        # print(fourth_nibble)
        print(f'{fourth_nibble:#06X}')

        match next_instruction_cat:
            case OpcodeCategory.FLOW_AND_SYSTEM:
                if next_instruction == OpCodes.CLEAR_SCREEN:
                    self.display_buffer = [0] * (64 * 32)
                    print('clear screen')
                elif next_instruction == OpCodes.RETURN:
                    print('return from a subroutine')
                else:
                    print('Empty Byte detected.')
            case OpcodeCategory.JUMP:
                self.PC[0] = second_nibble
                self.PC[1] = third_fourth_nibble
                print(f'jump to: {self.PC}')
            case OpcodeCategory.SET_CONSTANT:
                REGISTERS[second_nibble] = third_fourth_nibble
                print(f'set register general register: V{second_nibble} to {third_fourth_nibble}')
            case OpcodeCategory.ADD_CONSTANT:
                REGISTERS[second_nibble] = REGISTERS[second_nibble] + third_fourth_nibble & 0xFF
                print(f'Add: {third_fourth_nibble} to General Register: V{second_nibble}')
                print(f'New value is: {REGISTERS[second_nibble]}')
            case OpcodeCategory.MEMORY_INDEX:
                INDEX_REGISTER[0] = second_nibble
                INDEX_REGISTER[1] = third_fourth_nibble
                print(f'set memory index I to {INDEX_REGISTER}')
            case OpcodeCategory.DRAW:
                # FIXME: Implement draw
                print('Draw')

        print(next_instruction_address)
        pass


def load_font():
    """Load font into RAM"""
    # FIXME: Load font at start of RAM. Should be able to blit straight onto byte array.
    pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('CHIP8')
        self.cpu = EmulatedCPU()
        self.cpu.display_buffer[0] = 1
        self.cpu.display_buffer[-1] = 1
        self.view = EmulatedDisplay()
        self.view.pause_toggle_signal.connect(self.cpu.pause)
        self.cpu.render_signal.connect(self.view.update_screen)
        self.cpu.render_signal.emit(self.cpu.display_buffer.copy())
        self.cpu.start()
        self.setCentralWidget(self.view)
        self.adjustSize()
        self.setFixedSize(self.size())

    def closeEvent(self, a0):
        self.cpu.stop()
        self.cpu.quit()
        self.cpu.wait()
        super().closeEvent(a0)


if __name__ == '__main__':
    pass

    # pprint.pp(RAM)
    # RAM[0] = 15
    # # print(f'RAM: {RAM[0]:08b}')
    # # print(len(RAM))
    # # print(f'PC: {PC}')
    # # print(f'I: {INDEX_REGISTER}')
    # # print(f'Registers: {REGISTERS}')
    #
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
    # a = 0xA67B
    # b = a & 0x0FFF
    # print(hex(b))
