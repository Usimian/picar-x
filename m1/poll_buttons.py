import time
from time import sleep
from gpiozero import Button, LED
import logging
import sys
from gpiozero.pins.rpigpio import RPiGPIOFactory
import RPi.GPIO as GPIO
from test import run_servers
# from ledtest import run_led_test

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/picar-x.log')
    ]
)

# Initialize the button and LED
GPIO.cleanup()
GPIO.setwarnings(False)
sleep(0.5)  # Give time for cleanup to complete

button = Button(25)      # GPIO25 for input button
led = LED(26)           # GPIO26 for output LED

if __name__ == "__main__":
    try:
        led.on()
        logging.info("Starting button polling (Press CTRL+C to exit)...")
        logging.info("Main button on GPIO25, LED on GPIO26")
        
        while True:
            if button.is_pressed:
                led.off()
                led.close()
                # Force cleanup of all GPIO
                sleep(2)
                logging.info("GPIO resources released")
                logging.info("Starting Servers...")
                
                mqtt_server, video_server, ip = run_servers(block=False)

                while True:
                    if button.is_pressed:
                        cleanup(mqtt_server, video_server)
                        break


                # run_led_test()
                break
                
    except KeyboardInterrupt:
        logging.info("Stopping button polling...")
        led.off()
        led.close()
        button.close()
        GPIO.cleanup()
        logging.info("except GPIO resources released")
    finally:
        if 'led' in locals():
            led.close()
        if 'button' in locals():
            button.close()
        GPIO.cleanup()
        logging.info("finally GPIO resources released")
        sleep(0.5)  # Give time for cleanup to complete
        sys.exit(0)
