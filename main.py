"""
CHIP-8 interpreter implemented in python.

This program is built off the CHIP-8 interpreter specification. The CPU and I/O components(Key Input & Display Output)
are emulated. The CHIP-8 interpreter runs on top of the emulated CPU, receives input from emulated key Input, and then
outputs to an emulated display.

TODO:
    * Add Docstrings.
    * Write tests.
    * Make all the global vars class attributes unless I find display needs to access them directly.
    * Implement ROM loading.
    * Implement remaining Opcodes.
    * Add Step feature as debugging measure.
    * Add memory viewer that allows editing to aid debugging.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtCore import QThread
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem

from enum import IntEnum


class OpcodeCategory(IntEnum):
    """Enumerated OpCode Categories."""
    FLOW_AND_SYSTEM = 0x0
    JUMP = 0x1
    SET_CONSTANT = 0X6
    ADD_CONSTANT = 0X7
    MEMORY_INDEX = 0XA
    DRAW = 0XD


class OpCodes(IntEnum):
    """Enumerated Opcodes."""
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
"""Built-in Font"""

# TODO: Maybe should swap to tuple? I don't want the byte list to be mutable under any circumstances I dont think?
def byte_to_list(byte: int) -> list[int]:
    """Convert an integer into a list of digits that represent the integer in binary

    The byte(integer) is turned into an 8-bit padded binary string as an intermediate value, then that value is turned
    into a list of digits.
    """
    binary_string = f'{byte:08b}'
    binary_list = [int(char) for char in binary_string]
    return binary_list

def get_cur_pixel(x:int, y:int) -> int:
    """Convert a set of 2D screen coordinates to a 1D display buffer index."""
    return (y * 64) + x


class EmulatedDisplay(QGraphicsView):
    """Subclass and extend QGraphicsView to serve as emulated display output."""

    pause_toggle_signal = pyqtSignal(bool)
    """Custom Pause signal. Acts as a simple 2-way toggle."""

    def __init__(self, scale_factor=10):
        """Initialize the EmulatedDisplay class.

        Set up the emulated display. Set resolution and scale factor. Initialize the display buffer. Create underlying
        Image, PixMap, and Scene items used by PyQt.
        TODO: Add attribute docstrings when I move the global vars.
        """
        super().__init__()
        self.px_width = 64
        """Pre-scaled screen width"""

        self.px_height = 32
        """Pre-scaled screen height"""

        self.scale_factor = scale_factor
        """Upscale by this factor."""

        self.bytes_buffer = bytearray(2048)
        """Emulated display's video buffer."""

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.pixmap_item = QGraphicsPixmapItem()
        """Will hold memory mapped representation of the image."""

        self.image = QImage(self.bytes_buffer, self.px_width, self.px_height, self.px_width,
                            QImage.Format.Format_Grayscale8)
        """Base image, built directly through video buffer."""

        self.scene = QGraphicsScene()
        """The actual canvas used for display."""

        self.pixmap_item.setPixmap(QPixmap.fromImage(self.image))
        self.scene.addItem(self.pixmap_item)
        self.setScene(self.scene)
        self.scale(self.scale_factor, self.scale_factor)
        self.setFixedSize(self.px_width * self.scale_factor, self.px_height * self.scale_factor)

    def update_screen(self, frame_buffer: list) -> None:
        """Update the emulated display.

        Translate binary frame buffer list to 2-color grayscale.
        TODO: I barely remember why I chose grayscale over mono and that's a problem. Look into this again. I think
            I decided having access to so much space made optimizing for mono not make sense. Grayscale is easier to
            map a bytearray to because it expects ints between 0-255? Pretty sure that was it.

        """
        self.bytes_buffer = bytearray([255 if x == 1 else 0 for x in frame_buffer])
        self.image = QImage(self.bytes_buffer, self.px_width, self.px_height, self.px_width,
                            QImage.Format.Format_Grayscale8)
        self.pixmap_item.setPixmap(QPixmap.fromImage(self.image))

    def keyPressEvent(self, event):
        """Intercept keypress event and toggle pause."""
        if event.key() == Qt.Key.Key_P:
            self.pause_toggle_signal.emit(True)


class EmulatedCPU(QThread):
    """Subclass and extend QThread to serve as emulated cpu."""
    render_signal = pyqtSignal(list)

    def __init__(self):
        """Initialize the EmulatedCPU class

        Initialize the data structures and timing constants required by the CHIP-8 interpreter, as well as the emulated
        CPU the interpreter runs on.
        """
        super().__init__()
        self.PC = bytearray(2)
        """12 bit address pointing to current instruction in memory. Actually 16 bits, but never uses more than 12."""

        self.RAM = bytearray(4096)
        """4kB of 'RAM'"""

        self.index_register = bytearray(2)
        """12 bit index register. Actually 16 bits, but never uses more than 12."""

        self.subroutine_stack = []
        """Stack that holds 16 bit addresses pointing to subroutines(functions)"""

        self.delay_timer = 0
        """An 8-bit delay timer which is decremented at a rate of 60 Hz (60 times per second) until it reaches 0"""

        self.sound_timer = 0
        """An 8-bit sound timer which functions like the delay timer, but which also gives off a beeping sound as long as it’s not 0"""

        self.registers = bytearray(16)
        """16 8-bit gen purpose registers. VF used for flags."""

        self.PC[0] = 0x02
        self.paused = False
        """Pause Flag."""
        self.running = True
        """CPU Running Flag"""
        self.display_buffer = [0] * (64 * 32)
        """1D video buffer."""

        # Timing constants
        self.clock_speed = 700
        self.frame_rate = 60
        self.cycles_per_frame = int(self.clock_speed / self.frame_rate)

    def load_ibm_rom(self, ibm_rom_path) -> None:
        """Blit IBM logo test into RAM"""
        with open(rf"{ibm_rom_path}", 'rb') as file:
            rom_data = file.read()
            rom_size = len(rom_data)
            self.RAM[0x200:(0x200 + rom_size)] = rom_data

    def load_font(self) -> None:
        """Blit font into RAM"""
        self.RAM[:80] = font

    def run(self):
        """Override and extend the QThread run method.

        The CPU execution loop. Timing constraints are applied, OpCodes are fetched, decoded, and executed based on
        the aforementioned timing constraints. A signal is sent to the main thread(GUI) at regular intervals. The signal
        carries a copy of the display buffer, which the GUI thread can then use to update the emulated display.
        """
        # FIXME WTH is this doing here??!! Actual confusion.
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

    def pause(self) -> None:
        """Toggle pause state of emulated CPU.

        TODO: I believe the last cycle burst finishes before pausing. I should look into it and decide if this behavior
            is what I want.
        """
        if not self.paused:
            self.paused = True
        else:
            self.paused = False


    def stop(self) -> None:
        """Stop Emulated CPU from running.

        Helper function used to gracefully close when GUI window exists.
        """
        self.running = False

    def draw(self, x_register: int, y_register: int, sprite_height: int, display_buffer: list[int]) -> None:
        """DXYN opcode logic

         This instruction is somewhat involved.
         TODO: I'll come back when I'm ready to take another look at my approach. I want to clean up var names and possibly
            swap to bitwise XOR to flip bits. Will have to weigh readability vs efficiency I think.
         """
        # TODO Should probably make shifting to combine bytes into a function. Maybe even a getter and setter?
        #  That way everytime the value is accessed it will automatically combine them and everytime the value is set
        #  the value will be split over 2 bytes.
        sprite_start = self.index_register[0] << 8 | self.index_register[1]
        x_start = self.registers[x_register]
        y_start = self.registers[y_register]
        self.registers[15] = 0
        for row in range(sprite_height):
            y = y_start + row
            if y >= 32:
                break
            cur_byte = self.RAM[sprite_start + row]
            bit_list = byte_to_list(cur_byte)
            for bit_index in range(8):
                bit = bit_list[bit_index]
                if bit:
                    x = x_start + bit_index
                    if x >= 64:
                        break
                    cur_pixel = get_cur_pixel(x, y)
                    if display_buffer[cur_pixel] == 1:
                        display_buffer[cur_pixel] = 0
                        self.registers[15] = 1
                    else:
                        display_buffer[cur_pixel] = 1


    # TODO This needs a heavy refactor for clarity. Extend docstring whenever I get to refactoring.
    def fetch_decode_execute(self):
        """Fetch, decode, and execute OpCodes from RAM."""
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
        next_instruction = self.RAM[next_instruction_address] << 8 | self.RAM[next_instruction_address + 1]

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
        print(f'{second_nibble:#06X}')
        print(f'{third_nibble:#06X}')
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
                self.registers[second_nibble] = third_fourth_nibble
                print(f'set register general register: V{second_nibble} to {third_fourth_nibble}')

            case OpcodeCategory.ADD_CONSTANT:
                self.registers[second_nibble] = self.registers[second_nibble] + third_fourth_nibble & 0xFF
                print(f'Add: {third_fourth_nibble} to General Register: V{second_nibble}')
                print(f'New value is: {self.registers[second_nibble]}')

            case OpcodeCategory.MEMORY_INDEX:
                self.index_register[0] = second_nibble
                self.index_register[1] = third_fourth_nibble
                print(f'set memory index I to {self.index_register}')

            case OpcodeCategory.DRAW:
                self.draw(second_nibble, third_nibble, fourth_nibble, self.display_buffer)

        print(next_instruction_address)


class MainWindow(QMainWindow):
    def __init__(self):
        """Initialize the main GUI window and the components of the CHIP-8 Emulator.

        Create emulated CPU and Display. Connect signals between CPU thread and GUI. Start CPU.
        """
        super().__init__()
        self.setWindowTitle('CHIP8')
        self.cpu = EmulatedCPU()
        self.view = EmulatedDisplay()
        self.view.pause_toggle_signal.connect(self.cpu.pause)
        self.cpu.render_signal.connect(self.view.update_screen)
        self.cpu.render_signal.emit(self.cpu.display_buffer.copy())
        self.cpu.load_ibm_rom(r"C:\Users\kazac\Downloads\IBM Logo.ch8")
        self.cpu.start()
        self.setCentralWidget(self.view)
        self.adjustSize()
        self.setFixedSize(self.size())

    def closeEvent(self, a0):
        """Extend closeEvent to gracefully stop emulated CPU thread before closing main GUI thread."""
        self.cpu.stop()
        self.cpu.quit()
        self.cpu.wait()
        super().closeEvent(a0)


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()

