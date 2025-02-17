from server import PiServer
from robot_hat import ADC
from video_server import VideoServer
import time
import signal
import sys
import threading
import socket

def signal_handler(sig, frame):
    print('\nStopping servers...')
    if server:
        server.stop()
    if video_server:
        video_server.stop()
    sys.exit(0)

# Initialize ADC for battery monitoring
try:
    adc = ADC('A4')
except Exception as e:
    print(f"Error initializing ADC: {e}")
    adc = None

# Initialize servers
server = None
video_server = None

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

def get_ip_address():
    """Get the primary IP address of the device"""
    try:
        # Create a socket to get the IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't need to be reachable, just used to get local IP
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f"Error getting IP address: {e}")
        return "localhost"

if __name__ == "__main__":
    try:
        print("Starting PiCar-X Servers...")
        
        # Get IP address
        ip_address = get_ip_address()
        
        # Start MQTT server
        server = PiServer()
        server.start()
        
        # Start video server
        video_server = VideoServer(vflip=False, hflip=False)
        video_server.start()
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        
        # Start battery voltage update thread
        voltage_thread = threading.Thread(target=update_battery_voltage)
        voltage_thread.daemon = True
        voltage_thread.start()
        
        print("\nServers are running. Press Ctrl+C to stop.")
        print(f"Video stream available at:")
        print(f"  http://{ip_address}:9000/mjpg")
        print(f"  http://localhost:9000/mjpg")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if server:
            server.stop()
        if video_server:
            video_server.stop()
