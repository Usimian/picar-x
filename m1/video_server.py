#!/usr/bin/env python3

import os
import sys
from time import sleep, strftime, localtime
import cv2
import numpy as np
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import io
from PIL import Image
import logging

# Global flag for test pattern mode
USING_TEST_PATTERN = False

# Check if we're in a headless environment
HEADLESS = "DISPLAY" not in os.environ

# Web server configuration
WEB_PORT = 9000
WEB_HOST = '0.0.0.0'  # Listen on all interfaces
WEB_DISPLAY_HOST = '192.168.1.167'  # Display host for URLs

# Get logger for this module
logger = logging.getLogger('picar-x.video')
logger.setLevel(logging.INFO)

class TestPatternHandler(BaseHTTPRequestHandler):
    """HTTP request handler for serving test pattern"""
    def do_GET(self):
        if self.path == '/mjpg':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--frame')
            self.end_headers()
            try:
                while True:
                    if not hasattr(self.server, 'frame') or self.server.frame is None:
                        logger.info("Waiting for frame...")
                        sleep(0.033)
                        continue
                    
                    # Add validation check for frame
                    if not isinstance(self.server.frame, np.ndarray):
                        logger.error("Invalid frame format")
                        sleep(0.033)
                        continue
                        
                    # Convert frame to JPEG
                    img = Image.fromarray(cv2.cvtColor(self.server.frame, cv2.COLOR_BGR2RGB))
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='JPEG')
                    frame_data = img_bytes.getvalue()
                    
                    # Send frame with proper MIME multipart format
                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                    self.wfile.write(f'Content-Length: {len(frame_data)}\r\n\r\n'.encode())
                    self.wfile.write(frame_data)
                    self.wfile.write(b'\r\n')
                    sleep(0.033)  # ~30 fps
            except BrokenPipeError:
                logger.info("Client disconnected")  # Expected behavior
            except ConnectionResetError:
                logger.info("Connection reset by client")  # Expected behavior
            except Exception as e:
                logger.error(f"Unexpected error in video streaming: {e}")
        else:
            self.send_response(404)
            self.end_headers()

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread"""
    daemon_threads = True
    timeout = 60  # Longer timeout for connections

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
                logger.info(f"Web stream available at http://{WEB_DISPLAY_HOST}:{WEB_PORT}/mjpg")
            except Exception as e:
                logger.error(f"Error starting web server: {e}")
    
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
            logger.warning("Warning: Local display disabled in headless environment")
        
        self.running = False
        
        # Check vilib availability
        self.has_vilib, self.Vilib = self._check_vilib_available()
        # self.has_vilib = False
        # self.Vilib = None
        self.using_test_pattern = not self.has_vilib

        # Use MockVilib if real Vilib is not available
        self.vilib = MockVilib if not self.has_vilib else self.Vilib
        
        # Thread for test pattern updates
        self._test_pattern_thread = None
        
        # Store the test pattern image once generated
        self._test_pattern_image = None
    
    def _check_vilib_available(self):
        """Check if vilib is available and return appropriate video handler
        
        Returns:
            tuple: (bool, module) - (True, Vilib) if available, (False, None) if not
        """
        try:
            from vilib import Vilib
            logger.info("Successfully imported Vilib")
            return True, Vilib
        except (ImportError, IndexError) as e:
            logger.warning(f"Vilib not available: {e}")
            logger.info("Will use test pattern mode")
            return False, None

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
        # Generate the test pattern only once
        if self._test_pattern_image is None:
            self._test_pattern_image = self.generate_test_pattern()
            
        # Set the initial frame
        self.vilib.frame = self._test_pattern_image
        if self.vilib._web_server:
            self.vilib._web_server.frame = self.vilib.frame
            
        while self.running:
            try:
                # Just display the existing pattern, don't regenerate it
                if self.enable_local and not HEADLESS:
                    cv2.imshow('Test Pattern', self.vilib.frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                sleep(0.033)  # ~30 fps
            except Exception as e:
                logger.error(f"Error updating test pattern: {e}")
                break

    def start(self):
        """Start the video server"""
        try:
            logger.info("Starting video server...")
            
            # Set resolution through environment variable
            os.environ['VILIB_CAMERA_WIDTH'] = '320'
            os.environ['VILIB_CAMERA_HEIGHT'] = '240'
            
            if not self.using_test_pattern:
                try:
                    # Try to start camera with default resolution
                    self.vilib.camera_start(vflip=self.vflip, hflip=self.hflip)
                    
                    # Add a delay to ensure camera is fully initialized
                    logger.info("Waiting for camera to initialize...")
                    sleep(2)
                    
                    # Verify that flask_img is properly initialized
                    if not hasattr(self.vilib, 'flask_img') or self.vilib.flask_img is None:
                        logger.warning("Camera initialized but flask_img is not available")
                        raise Exception("Camera failed to initialize properly")
                    
                    # Additional check to ensure flask_img is a valid numpy array
                    if hasattr(self.vilib, 'flask_img'):
                        if not isinstance(self.vilib.flask_img, np.ndarray):
                            logger.warning(f"flask_img is not a numpy array: {type(self.vilib.flask_img)}")
                            raise Exception("Camera frame is in invalid format")
                    
                    logger.info("Camera initialized successfully")
                except Exception as camera_error:
                    logger.warning(f"Camera not available: {camera_error}")
                    logger.info("Falling back to test pattern")
                    self.using_test_pattern = True
                    self.vilib = MockVilib
            
            if self.using_test_pattern:
                # Generate test pattern once and store it
                self._test_pattern_image = self.generate_test_pattern()
                self.vilib.frame = self._test_pattern_image
                # Update mock status to indicate test pattern is in use
                try:
                    from server import MOCK_STATUS
                    MOCK_STATUS['camera'] = True
                except ImportError:
                    pass
            
            self.vilib.display(local=self.enable_local, web=self.enable_web)
            self.running = True
            logger.info("Video server started successfully")
            
            # Wait for initialization
            sleep(2)
            
            # If using test pattern, start update thread
            if self.using_test_pattern:
                self._test_pattern_thread = threading.Thread(target=self._update_test_pattern)
                self._test_pattern_thread.daemon = True
                self._test_pattern_thread.start()
                    
        except Exception as e:
            logger.error(f"Error starting video server: {e}")
            self.stop()

    def stop(self):
        """Stop the video server"""
        self.running = False
        
        # Wait for test pattern thread to stop
        if self._test_pattern_thread and self._test_pattern_thread.is_alive():
            self._test_pattern_thread.join(timeout=1.0)
        
        if self.using_test_pattern:
            if hasattr(self.vilib, '_web_server') and self.vilib._web_server:
                self.vilib._web_server.shutdown()
                self.vilib._web_server.server_close()
        else:
            self.vilib.camera_close()
        
        logger.info("Video server stopped")
