#!/usr/bin/env python3
from video_server import VideoServer

server = VideoServer()
server.start()
photo_path = server.take_photo()
print(f"Photo saved to: {photo_path}")
server.stop()
