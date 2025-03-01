import paho.mqtt.client as mqtt
import json
import threading
import time
import logging
import sys
from picarx import Picarx  # Import Picarx
from robot_hat import ADC
from gpio_functions import led  # Import LED from gpio_functions

# Get logger for this module
logger = logging.getLogger('picar-x.server')
logger.setLevel(logging.INFO)

MOCK_STATUS = {
    'gpio': False,        # GPIO/Motors mock status
    'i2c': False,         # I2C bus mock status
    'adc': False,         # ADC mock status
    'camera': False,      # Camera test pattern status
}

MQTT_BROKER = "localhost"  # MQTT broker address
MQTT_PORT = 1883  # Default MQTT port
TOPIC_CONTROL = "picar/control_request"  # Topic for receiving control commands
TOPIC_STATUS = "picar/status_request"  # Topic for receiving status requests

TOPIC_RESPONSE = "picar/status_response"  # Topic for sending status responses


class PiServer:
    def __init__(self, broker=MQTT_BROKER, port=MQTT_PORT):
        self.broker = broker
        self.port = port
        self.client = None
        self.running = False
        
        # Initialize Picarx
        try:
            self.px = Picarx()
        except Exception as e:
            logger.warning(f"Failed to initialize Picarx: {e}")
            self.px = None

        # Initialize ADC for battery monitoring
        try:
            self.adc = ADC('A4')
            logger.info("Initialized ADC")
        except Exception as e:
            logger.warning(f"Failed to initialize ADC: {e}")
            self.adc = None

        # Client variables for transfer
        self.slider_val = 0
        self.Vb = 0
        self.Pos = 0
        self.last_distance = 0.0  # Track last measured distance
        
        self.setup_mqtt()   # Setup MQTT client
        
        # Create battery voltage update thread
        self.voltage_thread = threading.Thread(target=self._update_battery_voltage)
        self.voltage_thread.daemon = True
        logger.debug("Voltage thread created")
        
        # Create ultrasonic distance update thread
        self.distance_thread = threading.Thread(target=self._update_distance)
        self.distance_thread.daemon = True
        logger.debug("Distance thread created")

    def _get_battery_voltage(self):
        """Read battery voltage from ADC"""
        try:
            led.on()    # Blink LED to indicate battery voltage reading
            time.sleep(0.1)
            led.off()

            if self.adc is None:
                return 0.0
            raw_value = self.adc.read()
            # Convert ADC value to voltage (assuming 3.3V reference)
            # and account for voltage divider if present
            voltage = raw_value * 3.3 / 4095 * 3  # multiply by 3 if using voltage divider
            return round(voltage, 2)
        except Exception as e:
            logger.error(f"Error reading ADC: {e}")
            return 0.0

    def _update_battery_voltage(self):
        """Update battery voltage in a loop"""
        while self.running:
            try:
                self.Vb = self._get_battery_voltage()
            except Exception as e:
                logger.error(f"Error updating battery voltage: {e}")
            time.sleep(1)  # Update every second

    def _update_distance(self):
        """Update distance measurement in a loop"""
        while self.running:
            try:
                if self.px:
                    self.last_distance = self.px.get_distance()
            except Exception as e:
                logger.error(f"Error updating distance: {e}")
            time.sleep(0.1)  # Update 10 times per second

    def setup_mqtt(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        logger.debug("setup_mqtt()")

    def on_connect(self, client, userdata, flags, rc):
        logger.info(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to control and status topics on connect/reconnect
        self.client.subscribe([
            (TOPIC_CONTROL, 0), 
            (TOPIC_STATUS, 0)
        ])
        logger.debug(f"Subscribed to topics: {TOPIC_CONTROL}, {TOPIC_STATUS}")

    def on_message(self, client, userdata, msg):
        try:
            logger.debug(f"--- Received Message: {msg.topic} ---")
            if msg.topic == TOPIC_STATUS:
                data = json.loads(msg.payload.decode())
                action = data.get('command', '')
                
                if action == 'status':
                    response = self.get_status()
                else:
                    logger.error(f'Unknown action: {action}')
                    return

                self.client.publish(TOPIC_RESPONSE, json.dumps(response))
                logger.debug(f"Published {action} response: {response}")
            elif msg.topic == TOPIC_CONTROL:
                # Handle control messages
                data = json.loads(msg.payload.decode())
                # print("Received control request:", data)
                
                # Handle motor control if x or y is present
                if ('speed' in data or 'turn' in data) and self.px is not None:
                    try:
                        x = data.get('turn', 0)  # For steering
                        y = data.get('speed', 0)  # For forward/backward movement
                        
                        # Convert x to steering angle (-40 to 40 degrees)
                        # Assuming x is in range -100 to 100
                        steering_angle = x * 20 # +/- 15 degrees
                        
                        # Set steering angle using servo 3
                        self.px.set_dir_servo_angle(steering_angle)
                        
                        # Convert y to motor speed (-100 to 100)
                        # Negative y means forward, positive y means backward
                        # Assuming y is in range -100 to 100
                        motor_speed = y*100.0
                        if motor_speed > 0 and self.last_distance > 10:
                            self.px.forward(motor_speed)
                        elif motor_speed < 0:
                            self.px.backward(abs(motor_speed))
                        else:
                            self.px.stop()
                        # print(f"Steering: {steering_angle:.0f}°, Speed: {motor_speed:.0f}")
                    except Exception as e:
                        logger.error(f"Error handling motor control: {e}")
                
                # Handle camera control if pan or tilt is present
                if ('pan' in data or 'tilt' in data) and self.px is not None:
                    try:
                        pan = data.get('pan', 0)
                        tilt = data.get('tilt', 0)
                        
                        # Convert to angles by dividing by 10
                        pan_angle = pan / 5
                        tilt_angle = tilt / 5
                        
                        # Set camera angles
                        self.px.set_cam_pan_angle(pan_angle)
                        self.px.set_cam_tilt_angle(tilt_angle)
                        # print(f"Pan: {pan_angle:.0f}, Tilt: {tilt_angle:.0f}")
                    except Exception as e:
                        logger.error(f"Error handling camera control: {e}")
                
                # Update other values based on control message
                for key, value in data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def get_status(self):
        return {
            'Vb': self.Vb,
            'distance': self.last_distance,
            'mock_status': MOCK_STATUS
        }

    def start(self):
        """Start the MQTT client and connect to broker"""
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            self.running = True
            logger.info(f"MQTT Server started on {self.broker}:{self.port}")

            # Start battery voltage monitoring thread
            self.voltage_thread.start()
            logger.debug("Voltage thread started")

            # Start distance monitoring thread
            self.distance_thread.start()
            logger.debug("Distance thread started")

        except Exception as e:
            logger.error(f"Error starting MQTT server: {e}")
            self.running = False

    def stop(self):
        """Stop the mqtt_server and cleanup"""
        self.running = False

        # Wait for distance thread to finish
        if self.distance_thread and self.distance_thread.is_alive():
            self.distance_thread.join(timeout=1.0)
        logger.debug("Distance thread stopped")
            
        # Wait for voltage thread to finish
        if self.voltage_thread and self.voltage_thread.is_alive():
            self.voltage_thread.join(timeout=1.0)
        logger.debug("Voltage thread stopped")
        
        # Stop MQTT client
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            
        logger.debug("mqtt_server stopped")
