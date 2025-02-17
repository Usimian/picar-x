from server import PiServer
from robot_hat import ADC
import time
import signal
import sys

def signal_handler(sig, frame):
    print('\nStopping server...')
    if server:
        server.stop()
    sys.exit(0)

# Initialize ADC for battery monitoring
try:
    adc = ADC('A4')
except Exception as e:
    print(f"Error initializing ADC: {e}")
    adc = None

# Initialize server
server = PiServer()

# Set up signal handler for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)

def get_battery_voltage():
    """Read battery voltage from ADC"""
    try:
        if adc is None:
            return 0.0
        raw_value = adc.read()
        # Convert ADC value to voltage (assuming 3.3V reference)
        # and account for voltage divider if present
        voltage = raw_value * 3.3 / 4095 * 3  # multiply by 3 if using voltage divider
        return round(voltage, 2)
    except Exception as e:
        print(f"Error reading ADC: {e}")
        return 0.0

def update_battery_voltage():
    """Update battery voltage reading periodically"""
    while True:
        try:
            # Get battery voltage from ADC
            voltage = get_battery_voltage()
            server.Vb = voltage
            time.sleep(1)  # Update every second
        except Exception as e:
            print(f"Error updating battery voltage: {e}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        print("Starting PiCar-X MQTT Server...")
        print("Press Ctrl+C to stop")
        
        # Start the MQTT server
        server.start()
        
        # Start updating battery voltage
        update_battery_voltage()
        
    except Exception as e:
        print(f"Error: {e}")
        server.stop()
