from server import PiServer
# from video_server import VideoServer
import time
import signal
import sys
import socket
from time import sleep
import logging
from gpiozero import Button, LED

# Global variables to track running servers
_running_servers = {
    'mqtt_server': None,
    'video_server': None,
    'ip_address': None
}

def setup_logging():
    """Set up logging configuration for the entire application"""
    # Configure root logger
    root_logger = logging.getLogger()
    if not root_logger.handlers:  # Only add handler if it doesn't exist
        root_logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # File handler
        file_handler = logging.FileHandler('/var/log/picar-x.log')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Get logger for this module
    logger = logging.getLogger('picar-x.test')
    logger.setLevel(logging.INFO)
    return logger

# Get module logger
logger = logging.getLogger('picar-x.test')

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

def cleanup(mqtt_server=None, video_server=None):
    """Clean shutdown of all services"""
    logger.info('Stopping services...')
    
    # Use global servers if none provided
    mqtt_server = mqtt_server or _running_servers['mqtt_server']
    video_server = video_server or _running_servers['video_server']
    
    # Stop the servers
    if mqtt_server:
        mqtt_server.stop()
    if video_server:
        video_server.stop()
    
    # Clear global servers
    _running_servers['mqtt_server'] = None
    _running_servers['video_server'] = None
    _running_servers['ip_address'] = None

def run_servers(block=True):
    """
    Start the PiCar-X servers
    
    Args:
        block (bool): If True, blocks and runs forever. If False, starts servers and returns.
    
    Returns:
        tuple: (mqtt_server, video_server, ip_address) if block=False
    """
    try:
        logger.info("Starting PiCar-X servers...")

        ip_address = get_ip_address()
        
        mqtt_server = PiServer()    # MQTT messaging system
        mqtt_server.start()

        video_server = None
        # video_server = VideoServer(vflip=False, hflip=False)
        # video_server.start()
        
        # Store running servers globally
        _running_servers.update({
            'mqtt_server': mqtt_server,
            'video_server': video_server,
            'ip_address': ip_address
        })

        # Set up signal handler for this process
        def signal_handler(sig, frame):
            cleanup()  # Use the global cleanup
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        # Also handle SIGTERM for proper systemd service shutdown
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info(f"Servers are running.")
        logger.info(f"Video stream available at: http://{ip_address}:9000/mjpg")

        if block:
            while True:
                time.sleep(1)
        else:
            return mqtt_server, video_server, ip_address

    except Exception as e:
        logger.error(f"Error: {e}")
        cleanup(mqtt_server, video_server)
        raise

if __name__ == "__main__":
    # Ensure logging is set up when run as main
    logger = setup_logging()
    
    try:
        # Start servers in non-blocking mode
        mqtt_server, video_server, ip = run_servers(block=False)
        
        # Keep the main thread alive to handle signals
        while True:
            try:
                sleep(1)
            except KeyboardInterrupt:
                logger.info("Received KeyboardInterrupt, shutting down...")
                break
    
    finally:
        # Ensure cleanup happens even if there's an error
        cleanup()
        logger.info("Shutdown complete")