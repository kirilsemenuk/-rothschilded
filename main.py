import tkinter as tk
from tkinter import ttk, messagebox

from serial_client import SerialClient
from test_runner import TestRunner
from reporter import save_report


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Hardware Validation Lab")
        self.root.geometry("900x650")

        self.client = SerialClient()

        self.build_ui()

    def build_ui(self):
        # Top control frame
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="x")

        ttk.Label(frame, text="COM Port:").grid(row=0, column=0, padx=5)

        self.port_entry = ttk.Entry(frame, width=15)
        self.port_entry.grid(row=0, column=1, padx=5)
        self.port_entry.insert(0, "COM4")

        ttk.Button(frame, text="Connect", command=self.connect).grid(row=0, column=2, padx=5)
        ttk.Button(frame, text="Run Tests", command=self.run_tests).grid(row=0, column=3, padx=5)
        ttk.Button(frame, text="Disconnect", command=self.disconnect).grid(row=0, column=4, padx=5)

        # Log window
        ttk.Label(self.root, text="Log").pack(anchor="w", padx=10)

        self.log = tk.Text(self.root, height=10)
        self.log.pack(fill="x", padx=10, pady=5)

        # Results table
        ttk.Label(self.root, text="Test Results").pack(anchor="w", padx=10)

        self.results_table = ttk.Treeview(
            self.root,
            columns=("test", "expected", "actual", "result"),
            show="headings",
            height=14
        )

        self.results_table.heading("test", text="Test")
        self.results_table.heading("expected", text="Expected")
        self.results_table.heading("actual", text="Actual")
        self.results_table.heading("result", text="Result")

        self.results_table.column("test", width=280)
        self.results_table.column("expected", width=280)
        self.results_table.column("actual", width=200)
        self.results_table.column("result", width=100, anchor="center")

        self.results_table.tag_configure("PASS", foreground="green")
        self.results_table.tag_configure("FAIL", foreground="red")

        self.results_table.pack(fill="both", expand=True, padx=10, pady=5)

    def connect(self):
        port = self.port_entry.get().strip()

        if not port:
            messagebox.showwarning("Warning", "Please enter a COM port")
            return

        try:
            self.client.connect(port)
            self.write_log(f"Connected to {port}")
        except Exception as e:
            self.write_log(f"Connection failed: {e}")
            messagebox.showerror("Connection Error", str(e))

    def disconnect(self):
        try:
            self.client.disconnect()
            self.write_log("Disconnected")
        except Exception as e:
            self.write_log(f"Disconnect error: {e}")

    def run_tests(self):
        if not self.client.is_connected():
            messagebox.showwarning("Warning", "Arduino is not connected")
            return

        # Clear previous table results
        for item in self.results_table.get_children():
            self.results_table.delete(item)

        self.write_log("")
        self.write_log("Running tests...")

        runner = TestRunner(self.client)
        results = runner.run_all_tests()

        passed_count = 0
        failed_count = 0

        for test in results:
            result = test["result"]

            if result == "PASS":
                passed_count += 1
            else:
                failed_count += 1

            self.write_log(f"{result} | {test['name']} | actual={test['actual']}")

            self.results_table.insert(
                "",
                "end",
                values=(
                    test["name"],
                    test["expected"],
                    test["actual"],
                    result
                ),
                tags=(result,)
            )

        report_path = save_report(results)

        self.write_log("")
        self.write_log(f"Summary: {passed_count} Passed, {failed_count} Failed")
        self.write_log(f"Report saved to: {report_path}")
        self.write_log("Done.")

    def write_log(self, message):
        self.log.insert("end", message + "\n")
        self.log.see("end")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()