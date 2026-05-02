class TestRunner:
    def __init__(self, client):
        self.client = client

    def run_test(self, name, command, expected):
        response = self.client.send_command(command)
        passed = expected in response

        return {
            "name": name,
            "command": command,
            "expected": expected,
            "actual": response,
            "result": "PASS" if passed else "FAIL"
        }

    def run_temperature_test(self):
        response = self.client.send_command("GET_TEMP")

        if "TEMP:" not in response:
            return {
                "name": "Temperature Range Test",
                "command": "GET_TEMP",
                "expected": "TEMP between 20 and 35",
                "actual": response,
                "result": "FAIL"
            }

        try:
            temp = float(response.split(":")[1])
            passed = 20 <= temp <= 35
        except ValueError:
            passed = False

        return {
            "name": "Temperature Range Test",
            "command": "GET_TEMP",
            "expected": "TEMP between 20 and 35",
            "actual": response,
            "result": "PASS" if passed else "FAIL"
        }

    def run_fault_sensor_test(self):
        response = self.client.send_command("FAULT_SENSOR")

        try:
            temp = float(response.split(":")[1])
            detected_fault = temp < -40 or temp > 100
        except Exception:
            detected_fault = True

        return {
            "name": "Fault Injection - Invalid Sensor Value",
            "command": "FAULT_SENSOR",
            "expected": "Fault detected",
            "actual": response,
            "result": "PASS" if detected_fault else "FAIL"
        }

    def run_fault_noise_test(self):
        response = self.client.send_command("FAULT_NOISE")

        detected_fault = "TEMP:" not in response

        return {
            "name": "Fault Injection - Corrupted Message",
            "command": "FAULT_NOISE",
            "expected": "Corrupted message detected",
            "actual": response,
            "result": "PASS" if detected_fault else "FAIL"
        }

    def run_all_tests(self):
        results = []

        results.append(self.run_test("Ping Test", "PING", "PONG"))
        results.append(self.run_test("LED ON Test", "LED_ON_B", "OK"))
        results.append(self.run_test("LED OFF Test", "LED_OFF_B", "OK"))
        results.append(self.run_temperature_test())
        results.append(self.run_test("Invalid Command Test", "HELLO", "ERROR"))

        results.append(self.run_fault_sensor_test())
        results.append(self.run_fault_noise_test())

        return results