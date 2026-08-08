"""
CHIP-8 Interpreter, implemented in python, via pyqt6.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtCore import QThread
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
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

class EmulatedDisplay(QGraphicsView):
    """Subclass and extend QGraphicsView to serve as emulated display output."""
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

        self.image = QImage(self.bytes_buffer, self.px_width, self.px_height, self.px_width, QImage.Format.Format_Grayscale8)
        self.scene = QGraphicsScene()
        self.pixmap_item.setPixmap(QPixmap.fromImage(self.image))
        self.scene.addItem(self.pixmap_item)
        self.setScene(self.scene)
        self.scale(self.scale_factor, self.scale_factor)
        self.setFixedSize(self.px_width * self.scale_factor, self.px_height * self.scale_factor)

    def update_screen(self, frame_buffer: list):
        self.bytes_buffer = bytearray([255 if x == 1 else 0 for x in frame_buffer])
        self.image = QImage(self.bytes_buffer, self.px_width, self.px_height, self.px_width, QImage.Format.Format_Grayscale8)
        self.pixmap_item.setPixmap(QPixmap.fromImage(self.image))

class EmulatedCPU(QThread):
    """Subclass and extend QThread to serve as emulated cpu."""
    render_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
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

    def fetch_decode_execute(self):
        pass


def load_font():
    """Load font into RAM"""
    pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('CHIP8')
        self.cpu = EmulatedCPU()
        self.cpu.display_buffer[0] = 1
        self.cpu.display_buffer[-1] = 1
        self.view = EmulatedDisplay()
        self.cpu.render_signal.connect(self.view.update_screen)
        self.cpu.render_signal.emit(self.cpu.display_buffer.copy())
        self.setCentralWidget(self.view)
        self.adjustSize()
        self.setFixedSize(self.size())

if __name__ == '__main__':
    RAM[0] = 15
    # print(f'RAM: {RAM[0]:08b}')
    # print(len(RAM))
    # print(f'PC: {PC}')
    # print(f'I: {INDEX_REGISTER}')
    # print(f'Registers: {REGISTERS}')

    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()

