import time
from time import sleep
from gpiozero import Button, LED
import logging
import sys
import RPi.GPIO as GPIO

# Get logger from poll_buttons.py
logger = logging.getLogger('picar-x.buttons')

def run_led_test():
    led = None
    try:
        # Force cleanup of all GPIO resources first
        GPIO.cleanup()
        GPIO.setwarnings(False)
        sleep(0.5)
        
        logger.info("Initializing LED on GPIO26")
        led = LED(26)    # GPIO26 for output LED
        button = Button(25)      # GPIO25 for input button

        # Initialize button
        logger.info("Blinking LED")
        # Blink LED to indicate test is starting
        for _ in range(10):
            led.toggle()
            sleep(0.1)
        led.on()    # Keep LED on for visual confirmation
    
        while True:
            if button.is_pressed:
                led.off()
                led.close()
                button.close()
                # Force cleanup of all GPIO
                sleep(2)
                logging.info("GPIO resources released")
                logging.info("Starting Server test...")
                break

    except Exception as e:
        logger.error(f"Error in LED test: {e}")
        
    finally:
        if led:
            led.close()
            logger.info("Close LED")
        GPIO.cleanup()
        logger.info("GPIO resources released")

if __name__ == "__main__":
    run_led_test()
