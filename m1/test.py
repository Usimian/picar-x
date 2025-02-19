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
    if mqtt_server:
        mqtt_server.stop()
    if video_server:
        video_server.stop()
    sys.exit(0)

# Initialize ADC for battery monitoring
try:
    adc = ADC('A4')
except Exception as e:
    print(f"Error initializing ADC: {e}")
    adc = None

# Initialize servers and shared objects
mqtt_server = None
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
            mqtt_server.Vb = voltage
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

def measure_distance():
    """Measure distance from ultrasonic sensor at 20Hz"""
    global mqtt_server
    if mqtt_server is None or mqtt_server.px is None:
        print("Error: Picarx not initialized")
        return

    interval = 0.05  # 20Hz measurement rate
    SAFETY_DISTANCE = 10  # cm
    
    while True:
        try:
            distance = mqtt_server.px.get_distance()
            # Safety check - stop if too close to obstacle
            if distance is not None and distance < SAFETY_DISTANCE:
                # Stop the car by setting speed to 0
                mqtt_server.px.forward(0)
                print(f"Safety stop! Obstacle detected at {distance:.1f} cm")
            time.sleep(interval)
        except Exception as e:
            print(f"Error measuring distance: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    try:
        print("Starting PiCar-X servers...")

        ip_address = get_ip_address()
        
        mqtt_server = PiServer()    # MQTT messaging system
        mqtt_server.start()

        video_server = VideoServer(vflip=False, hflip=False)
        video_server.start()

        signal.signal(signal.SIGINT, signal_handler)

        battery_voltage_thread = threading.Thread(target=update_battery_voltage)
        battery_voltage_thread.daemon = True
        battery_voltage_thread.start()

        if mqtt_server.px is not None:
            distance_thread = threading.Thread(target=measure_distance)
            distance_thread.daemon = True
            distance_thread.start()
        else:
            print("Warning: Distance measurement disabled due to Picarx initialization failure")

        print(f"\nServers are running. Press Ctrl+C to stop.")
        print(f"Video stream available at: http://{ip_address}:9000/mjpg")

        while True:
            time.sleep(1)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if mqtt_server:
            mqtt_server.stop()
        if video_server:
            video_server.stop()
