"""
GPIO functions for controlling buttons and LEDs
"""
from gpiozero import Button, LED
import logging

# Configure logging for this module
logger = logging.getLogger('picar-x.gpio_functions')

# Initialize the button and LED as global variables
button = Button(25)      # GPIO25 for input button
led = LED(26)           # GPIO26 for output LED


def setup_gpio():
    """Set up GPIO devices"""
    try:
        logger.info("GPIO devices initialized")
    except Exception as e:
        logger.error(f"Failed to initialize GPIO devices: {e}")
        raise


def cleanup_gpio():
    """Clean up GPIO resources"""
    if 'led' in locals() and led is not None:
        led.close()
    if 'button' in locals() and button is not None:
        button.close()
    logger.info("GPIO resources released")
