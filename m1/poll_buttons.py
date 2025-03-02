import time
from time import sleep
import logging
import sys
from test import run_servers, cleanup
from gpio_functions import button, led, setup_gpio

def setup_logging():
    """Set up logging configuration for the entire application"""
    try:
        # Configure root logger
        root_logger = logging.getLogger()
        
        # Clear any existing handlers to avoid duplicates
        root_logger.handlers = []
        
        root_logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        
        # File handler
        file_handler = logging.FileHandler('/var/log/picar-x.log')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
    except PermissionError:
        print("Error: Unable to write to /var/log/picar-x.log - Please run with appropriate permissions")
        sys.exit(1)
    except Exception as e:
        print(f"Error setting up logging: {e}")
        sys.exit(1)

# Set up logging first
setup_logging()

# Configure module logger
logger = logging.getLogger('picar-x.buttons')
logger.setLevel(logging.INFO)

# Initialize GPIO
setup_gpio()

if __name__ == "__main__":
    mqtt_server = None
    video_server = None
    try:
        led.on()
        logger.info("Starting button polling (Press CTRL+C to exit)...")

        while True:
            # Use wait_for_press instead of continuous polling
            button.wait_for_press() # Blocking call

            led.off()
            logger.info("Starting Servers")
            try:
                mqtt_server, video_server, ip = run_servers()
            except Exception as e:
                logger.error(f"Failed to start servers: {e}")
                mqtt_server = None
                video_server = None
                break

            # Second press - stop servers
            button.wait_for_press() # Blocking call

            logger.info("Start/stop pressed, shutting down")
            for _ in range(5):
                led.on()
                sleep(0.1)
                led.off()
                sleep(0.1)
            break

    except KeyboardInterrupt:
        logger.info("Ctrl-C detected, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        cleanup(mqtt_server, video_server)
        mqtt_server = None
        video_server = None
        sys.exit(0)
