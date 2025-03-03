from server import PiServer
from video_server import VideoServer
import time
import signal
import sys
import socket
from time import sleep
import logging
from gpio_functions import setup_gpio, cleanup_gpio, button, led

# Get logger for this module
logger = logging.getLogger('picar-x.test')
logger.setLevel(logging.DEBUG)

# Initialize GPIO
setup_gpio()

def cleanup(mqtt_server=None, video_server=None):
    """Clean shutdown of all services"""
    logger.info('Stopping services...')
    
    # Stop the servers
    if mqtt_server:
        mqtt_server.stop()
    if video_server:
        video_server.stop()
    
    # Cleanup GPIO
    cleanup_gpio()

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
        logger.error(f"Error getting IP address: {e}")
        return "localhost"

def run_servers():
    """
    Start the PiCar-X servers
    
    Returns:
        tuple: (mqtt_server, video_server, ip_address)
    """
    try:
        logger.debug("Starting PiCar-X - servers...")
        
        ip_address = get_ip_address()

        mqtt_server = None
        mqtt_server = PiServer()    # MQTT messaging system
        mqtt_server.start() # Start MQTT server

        video_server = None
        video_server = VideoServer(vflip=False, hflip=False)
        video_server.start()
        logger.debug(f"video_server.start() - ok")

        # Set up signal handler for this process
        def signal_handler(sig, frame):
            # cleanup()  # Use the global cleanup
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        # Also handle SIGTERM for proper systemd service shutdown
        signal.signal(signal.SIGTERM, signal_handler)

        return mqtt_server, video_server, ip_address

    except Exception as e:
        logger.error(f"Error: {e}")
        cleanup(mqtt_server, video_server)
        raise
