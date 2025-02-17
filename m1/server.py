import paho.mqtt.client as mqtt
import json
import threading
import time
from picarx import Picarx  # Import Picarx

# Hardware mock status flags
MOCK_STATUS = {
    'gpio': False,        # GPIO/Motors mock status
    'i2c': False,         # I2C bus mock status
    'adc': False,         # ADC mock status
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
            print(f"Warning: Failed to initialize Picarx: {e}")
            self.px = None

        # Client variables for transfer
        self.slider_val = 0
        self.Vb = 0
        self.Pos = 0
        
        # MQTT setup
        self.setup_mqtt()

    def setup_mqtt(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to control and status topics on connect/reconnect
        self.client.subscribe([(TOPIC_CONTROL, 0), (TOPIC_STATUS, 0)])
        print(f"Subscribed to topics: {TOPIC_CONTROL}, {TOPIC_STATUS}")

    def on_message(self, client, userdata, msg):
        try:
            print(f"\n--- Received Message: {msg.topic} ---")
            if msg.topic == TOPIC_STATUS:
                # Send current status with 2 significant digits
                response = {
                    "Vb": float(f"{self.Vb:.2f}"),  # Battery voltage from Picarx
                    "mock_status": MOCK_STATUS
                }
                self.client.publish(TOPIC_RESPONSE, json.dumps(response))
                print(f"Published status response: {response}")
            elif msg.topic == TOPIC_CONTROL:
                # Handle control messages
                data = json.loads(msg.payload.decode())
                print("Received control request:", data)
                
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
                        print(f"Camera angles set - pan: {pan_angle}, tilt: {tilt_angle}")
                    except Exception as e:
                        print(f"Error handling camera control: {e}")
                
                # Update other values based on control message
                for key, value in data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
        except Exception as e:
            print(f"Error processing message: {e}")

    def start(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.running = True
            
            # Start the MQTT loop in a background thread
            self.client.loop_start()
            
            # Start the publishing loop in a separate thread
            self.publish_thread = threading.Thread(target=self.publish_data)
            self.publish_thread.start()
            
            print(f"MQTT Server started on {self.broker}:{self.port}")
        except Exception as e:
            print(f"Failed to start server: {e}")
            self.stop()

    def stop(self):
        self.running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        print("Server stopped")

    def publish_data(self):
        while self.running:
            try:
                # Only publish on status request now
                time.sleep(0.1)  # Sleep to prevent busy loop
            except Exception as e:
                print(f"Error in publish loop: {e}")
                if not self.running:
                    break


# Usage example:
if __name__ == "__main__":
    server = PiServer()
    server.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
