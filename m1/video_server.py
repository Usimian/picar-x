#!/usr/bin/env python3

import os
import signal
import sys
from time import sleep, strftime, localtime
import cv2
import numpy as np
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import io
from PIL import Image

# Global flag for test pattern mode
USING_TEST_PATTERN = False

# Check if we're in a headless environment
HEADLESS = "DISPLAY" not in os.environ

# Web server configuration
WEB_PORT = 9000
WEB_HOST = '0.0.0.0'  # Listen on all interfaces
WEB_DISPLAY_HOST = '192.168.1.167'  # Display host for URLs

try:
    from vilib import Vilib
    print("Successfully imported Vilib")
    HAS_VILIB = True
except Exception as e:
    print(f"Warning: Vilib not available: {e}")
    print("Will use test pattern mode")
    HAS_VILIB = False

class TestPatternHandler(BaseHTTPRequestHandler):
    """HTTP request handler for serving test pattern"""
    def do_GET(self):
        print(f"Received request for {self.path}")
        if self.path == '/mjpg':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--frame')
            self.end_headers()
            try:
                while True:
                    if not hasattr(self.server, 'frame') or self.server.frame is None:
                        print("Waiting for frame...")
                        sleep(0.033)
                        continue
                    
                    # Convert frame to JPEG
                    img = Image.fromarray(cv2.cvtColor(self.server.frame, cv2.COLOR_BGR2RGB))
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='JPEG')
                    frame_data = img_bytes.getvalue()
                    
                    # Send frame
                    self.wfile.write(b'--frame\r\n')
                    self.send_header('Content-type', 'image/jpeg')
                    self.send_header('Content-length', len(frame_data))
                    self.end_headers()
                    self.wfile.write(frame_data)
                    self.wfile.write(b'\r\n')
                    sleep(0.033)  # ~30 fps
            except Exception as e:
                print(f"Error in video streaming: {e}")
                pass
        else:
            self.send_response(404)
            self.end_headers()

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread"""
    daemon_threads = True

class MockVilib:
    """Mock Vilib class for test pattern mode"""
    frame = None
    _web_server = None
    _web_thread = None
    
    @classmethod
    def display(cls, local=True, web=True):
        if local and not HEADLESS:
            cv2.namedWindow('Test Pattern', cv2.WINDOW_NORMAL)
        
        if web:
            try:
                # Start web server
                cls._web_server = ThreadedHTTPServer((WEB_HOST, WEB_PORT), TestPatternHandler)
                cls._web_server.frame = cls.frame  # Share the frame with the handler
                cls._web_thread = threading.Thread(target=cls._web_server.serve_forever)
                cls._web_thread.daemon = True
                cls._web_thread.start()
                print(f"Web stream available at http://{WEB_DISPLAY_HOST}:{WEB_PORT}/mjpg")
            except Exception as e:
                print(f"Error starting web server: {e}")
    
    @staticmethod
    def camera_start(**kwargs):
        pass
    
    @classmethod
    def camera_close(cls):
        if not HEADLESS:
            cv2.destroyAllWindows()
        
        if cls._web_server:
            cls._web_server.shutdown()
            cls._web_server.server_close()

class VideoServer:
    def __init__(self, vflip=False, hflip=False, enable_web=True, enable_local=True):
        """Initialize the video server
        
        Args:
            vflip (bool): Flip video vertically
            hflip (bool): Flip video horizontally
            enable_web (bool): Enable web streaming
            enable_local (bool): Enable local display
        """
        self.vflip = vflip
        self.hflip = hflip
        self.enable_web = enable_web
        # Disable local display in headless environment
        self.enable_local = enable_local and not HEADLESS
        if enable_local and HEADLESS:
            print("Warning: Local display disabled in headless environment")
        
        self.running = False
        self.using_test_pattern = not HAS_VILIB
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Get user home directory for photos
        user = os.getlogin()
        self.photo_path = os.path.expanduser(f'~{user}/Pictures/picar-x/')
        
        # Ensure photo directory exists
        os.makedirs(self.photo_path, exist_ok=True)
        
        # Use MockVilib if real Vilib is not available
        self.vilib = MockVilib if not HAS_VILIB else Vilib
        
        # Thread for test pattern updates
        self._test_pattern_thread = None

    def generate_test_pattern(self):
        """Generate a test pattern image
        
        Returns:
            numpy.ndarray: Test pattern image
        """
        width = int(os.environ.get('VILIB_CAMERA_WIDTH', '320'))
        height = int(os.environ.get('VILIB_CAMERA_HEIGHT', '240'))
        
        # Create a color test pattern
        pattern = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add color bars
        bar_width = width // 8
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (0, 255, 255),  # Cyan
            (255, 0, 255),  # Magenta
            (255, 255, 255),# White
            (0, 0, 0)       # Black
        ]
        
        for i, color in enumerate(colors):
            x1 = i * bar_width
            x2 = (i + 1) * bar_width
            pattern[:, x1:x2] = color
            
        # Add text
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(pattern, 'NO CAMERA', (width//4, height//2), 
                   font, 1, (255, 255, 255), 2)
        cv2.putText(pattern, 'TEST PATTERN', (width//4, height//2 + 40), 
                   font, 1, (255, 255, 255), 2)
        
        return pattern

    def _update_test_pattern(self):
        """Update test pattern in a loop"""
        print("Starting test pattern update loop")
        while self.running:
            try:
                self.vilib.frame = self.generate_test_pattern()
                if self.vilib._web_server:
                    self.vilib._web_server.frame = self.vilib.frame
                if self.enable_local and not HEADLESS:
                    cv2.imshow('Test Pattern', self.vilib.frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                sleep(0.033)  # ~30 fps
            except Exception as e:
                print(f"Error updating test pattern: {e}")
                break

    def start(self):
        """Start the video server"""
        try:
            print("Starting video server...")
            
            # Set resolution through environment variable
            os.environ['VILIB_CAMERA_WIDTH'] = '320'
            os.environ['VILIB_CAMERA_HEIGHT'] = '240'
            
            if not self.using_test_pattern:
                try:
                    # Try to start camera with default resolution
                    self.vilib.camera_start(vflip=self.vflip, hflip=self.hflip)
                except Exception as camera_error:
                    print(f"Camera not available: {camera_error}")
                    print("Falling back to test pattern")
                    self.using_test_pattern = True
                    self.vilib = MockVilib
            
            if self.using_test_pattern:
                # Initialize with test pattern
                test_pattern = self.generate_test_pattern()
                self.vilib.frame = test_pattern
                # Update mock status to indicate test pattern is in use
                try:
                    from server import MOCK_STATUS
                    MOCK_STATUS['camera'] = True
                except ImportError:
                    pass
            
            self.vilib.display(local=self.enable_local, web=self.enable_web)
            self.running = True
            print("Video server started successfully")
            print(f"Using {'test pattern' if self.using_test_pattern else 'camera'} mode")
            
            # Wait for initialization
            sleep(2)
            
            # If using test pattern, start update thread
            if self.using_test_pattern:
                self._test_pattern_thread = threading.Thread(target=self._update_test_pattern)
                self._test_pattern_thread.daemon = True
                self._test_pattern_thread.start()
                    
        except Exception as e:
            print(f"Error starting video server: {e}")
            self.stop()

    def stop(self):
        """Stop the video server"""
        self.running = False
        try:
            # Wait for test pattern thread to finish
            if self._test_pattern_thread is not None:
                self._test_pattern_thread.join(timeout=1.0)
            
            if not self.using_test_pattern:
                self.vilib.camera_close()
            elif not HEADLESS:
                cv2.destroyAllWindows()
                # Reset mock status when stopping test pattern
                try:
                    from server import MOCK_STATUS
                    MOCK_STATUS['camera'] = False
                except ImportError:
                    pass
            print("Video server stopped")
        except Exception as e:
            print(f"Error stopping video server: {e}")

    def take_photo(self):
        """Take a photo and save it
        
        Returns:
            str: Path to saved photo
        """
        try:
            timestamp = strftime('%Y-%m-%d-%H-%M-%S', localtime())
            name = f'photo_{timestamp}'
            
            if self.using_test_pattern:
                # Save test pattern directly
                photo_path = f"{self.photo_path}{name}.jpg"
                cv2.imwrite(photo_path, self.generate_test_pattern())
            else:
                # Use Vilib's photo function
                self.vilib.take_photo(name, self.photo_path)
                photo_path = f"{self.photo_path}{name}.jpg"
                
            print(f'Photo saved as {photo_path}')
            return photo_path
        except Exception as e:
            print(f"Error taking photo: {e}")
            return None

    def _signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        print('\nStopping video server...')
        self.stop()
        sys.exit(0)

if __name__ == "__main__":
    # Example usage
    server = VideoServer(vflip=False, hflip=False)
    try:
        server.start()
        print("\nPress Ctrl+C to stop the server")
        while server.running:
            sleep(1)
    except KeyboardInterrupt:
        server.stop()
