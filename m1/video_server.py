#!/usr/bin/env python3

import os
import signal
import sys
from time import sleep, strftime, localtime

try:
    from vilib import Vilib
    print("Successfully imported Vilib")
except Exception as e:
    print(f"Error importing Vilib: {e}")
    raise

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
        self.enable_local = enable_local
        self.running = False
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Get user home directory for photos
        user = os.getlogin()
        self.photo_path = os.path.expanduser(f'~{user}/Pictures/picar-x/')
        
        # Ensure photo directory exists
        os.makedirs(self.photo_path, exist_ok=True)

    def start(self):
        """Start the video server"""
        try:
            print("Starting video server...")
            Vilib.camera_start(vflip=self.vflip, hflip=self.hflip)
            Vilib.display(local=self.enable_local, web=self.enable_web)
            self.running = True
            print("Video server started successfully")
            
            # Wait for camera to initialize
            sleep(2)
            
            if self.enable_web:
                print("Web stream available at http://localhost:9000/mjpg")
        except Exception as e:
            print(f"Error starting video server: {e}")
            self.stop()

    def stop(self):
        """Stop the video server"""
        self.running = False
        try:
            Vilib.camera_close()
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
            Vilib.take_photo(name, self.photo_path)
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
