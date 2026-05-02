import serial
import time


class SerialClient:
    def __init__(self):
        self.connection = None

    def connect(self, port):
        self.connection = serial.Serial(port, 115200, timeout=2)
        time.sleep(2)
        self.connection.reset_input_buffer()
        self.connection.reset_output_buffer()

    def disconnect(self):
        if self.connection and self.connection.is_open:
            self.connection.close()

    def is_connected(self):
        return self.connection is not None and self.connection.is_open

    def send_command(self, command):
        if not self.is_connected():
            return "NOT_CONNECTED"

        # Clear old data
        self.connection.reset_input_buffer()

        # Send command
        self.connection.write((command + "\n").encode("ascii"))

        # Read several lines and ignore READY
        for _ in range(5):
            response = self.connection.readline().decode("ascii", errors="ignore").strip()

            if not response:
                continue

            if response == "READY":
                continue

            return response

        return "NO_RESPONSE"