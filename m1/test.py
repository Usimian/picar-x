from server import PiServer
from robot_hat import ADC
from video_server import VideoServer
import time
import signal
import sys
import threading
import socket
from time import sleep


def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

# Initialize servers and shared objects
mqtt_server = None
video_server = None
distance_thread_running = True  # Global flag to control distance thread
_cleanup_done = False  # Flag to track if cleanup has been done

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
    global mqtt_server, distance_thread_running
    if mqtt_server is None or mqtt_server.px is None:
        print("Error: Picarx not initialized")
        return

    interval = 0.05  # 20Hz measurement rate
    SAFETY_DISTANCE = 10  # cm
    
    while distance_thread_running:  # Use our own control flag
        try:
            if mqtt_server and mqtt_server.px:  # Check if server and px are still available
                distance = mqtt_server.px.get_distance()
                # Safety check - stop if too close to obstacle
                if distance is not None and distance < SAFETY_DISTANCE:
                    # Stop the car by setting speed to 0
                    mqtt_server.px.forward(0)
            time.sleep(interval)
        except Exception as e:
            if distance_thread_running:  # Only print error if we're still supposed to be running
                print(f"Error measuring distance: {e}")
            time.sleep(interval)

def cleanup():
    """Clean shutdown of all services"""
    global distance_thread_running, _cleanup_done
    
    # Only cleanup once
    if _cleanup_done:
        return
    _cleanup_done = True
    
    print('\nStopping services...')
    
    # First stop the distance thread
    distance_thread_running = False
    if 'distance_thread' in globals() and distance_thread:
        time.sleep(0.2)  # Give the thread time to stop
    print("Distance thread stopped")
    
    # Then stop the servers
    if mqtt_server:
        mqtt_server.stop()
    if video_server:
        video_server.stop()

if __name__ == "__main__":
    distance_thread = None  # Initialize thread variable
    try:
        print("Starting PiCar-X servers...")

        ip_address = get_ip_address()
        
        mqtt_server = PiServer()    # MQTT messaging system
        mqtt_server.start()

        video_server = VideoServer(vflip=False, hflip=False)
        video_server.start()

        signal.signal(signal.SIGINT, signal_handler)

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
        cleanup()