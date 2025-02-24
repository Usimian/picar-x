import paho.mqtt.client as mqtt
import json
import threading
import time
import logging
import sys
from picarx import Picarx  # Import Picarx
from robot_hat import ADC
from gpiozero import LED

# Configure logging
logger = logging.getLogger('picar-x.server')
logger.setLevel(logging.DEBUG)

# Add handlers if they don't exist
if not logger.handlers:
    # Create formatters and handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # File handler
    file_handler = logging.FileHandler('/var/log/picar-x.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

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
TOPIC_STATUS_INFO = "picar/status_info"  # Topic for receiving status info requests
TOPIC_RESPONSE = "picar/status_response"  # Topic for sending status responses


class PiServer:
    def __init__(self, broker=MQTT_BROKER, port=MQTT_PORT):
        self.broker = broker
        self.port = port
        self.client = None
        self.running = False
        
        # Initialize LED for battery monitoring
        try:
            self.battery_led = LED(26)
        except Exception as e:
            logger.warning(f"Failed to initialize LED: {e}")
            self.battery_led = None

        # Initialize Picarx
        try:
            self.px = Picarx()
        except Exception as e:
            logger.warning(f"Failed to initialize Picarx: {e}")
            self.px = None

        # Initialize ADC for battery monitoring
        try:
            self.adc = ADC('A4')
        except Exception as e:
            logger.warning(f"Failed to initialize ADC: {e}")
            self.adc = None

        # Client variables for transfer
        self.slider_val = 0
        self.Vb = 0
        self.Pos = 0
        self.last_distance = 0.0  # Track last measured distance
        
        # MQTT setup
        self.setup_mqtt()
        
        # Create battery voltage update thread
        self.voltage_thread = threading.Thread(target=self._update_battery_voltage)
        self.voltage_thread.daemon = True
        
        # Create distance update thread
        self.distance_thread = threading.Thread(target=self._update_distance)
        self.distance_thread.daemon = True

    def _get_battery_voltage(self):
        """Read battery voltage from ADC"""
        try:
            if self.battery_led:
                self.battery_led.on()    # Blink LED to indicate battery voltage reading
                time.sleep(0.1)
                self.battery_led.off()

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
        
    def on_connect(self, client, userdata, flags, rc):
        logger.info(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to control and status topics on connect/reconnect
        self.client.subscribe([
            (TOPIC_CONTROL, 0), 
            (TOPIC_STATUS, 0),
            (TOPIC_STATUS_INFO, 0)
        ])
        logger.info(f"Subscribed to topics: {TOPIC_CONTROL}, {TOPIC_STATUS}, {TOPIC_STATUS_INFO}")

    def on_message(self, client, userdata, msg):
        try:
            # print(f"\n--- Received Message: {msg.topic} ---")
            if msg.topic == TOPIC_STATUS_INFO:
                # Get current distance measurement
                if self.px:
                    try:
                        self.last_distance = self.px.get_distance()
                    except Exception as e:
                        logger.error(f"Error reading distance: {e}")
                
                # Send status response with battery and distance
                response = {
                    "Vb": float(f"{self.Vb:.2f}"),  # Battery voltage from ADC
                    "distance": float(f"{self.last_distance:.2f}")  # Last measured distance
                }
                self.client.publish(TOPIC_RESPONSE, json.dumps(response))
                logger.debug(f"Published status info response: {response}")
            
            elif msg.topic == TOPIC_STATUS:
                # Send current status with 2 significant digits
                response = {
                    "Vb": float(f"{self.Vb:.2f}"),  # Battery voltage from ADC
                    "mock_status": MOCK_STATUS
                }
                self.client.publish(TOPIC_RESPONSE, json.dumps(response))
                logger.debug(f"Published status response: {response}")
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
                        steering_angle = x * 15 # +/- 15 degrees
                        
                        # Set steering angle using servo 3
                        self.px.set_dir_servo_angle(steering_angle)
                        
                        # Convert y to motor speed (-100 to 100)
                        # Negative y means forward, positive y means backward
                        # Assuming y is in range -100 to 100
                        motor_speed = y*100.0
                        
                        if motor_speed > 0:
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

    def start(self):
        """Start the MQTT client and connect to broker"""
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            self.running = True
            # Start battery voltage monitoring thread
            self.voltage_thread.start()
            # Start distance monitoring thread
            self.distance_thread.start()
            logger.info(f"MQTT Server started on {self.broker}:{self.port}")
        except Exception as e:
            logger.error(f"Error starting MQTT server: {e}")
            self.running = False

    def stop(self):
        """Stop the mqtt_server and cleanup"""
        self.running = False
        
        # Wait for voltage thread to finish
        if self.voltage_thread and self.voltage_thread.is_alive():
            self.voltage_thread.join(timeout=1.0)
        logger.info("Voltage thread stopped")
        
        # Wait for distance thread to finish
        if self.distance_thread and self.distance_thread.is_alive():
            self.distance_thread.join(timeout=1.0)
        logger.info("Distance thread stopped")
            
        # Stop MQTT client
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            
        logger.info("mqtt_server stopped")
