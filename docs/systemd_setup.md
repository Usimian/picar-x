# Setting up Systemd Service for PiCar-X

This guide explains how to configure and manage the systemd service for autostarting PiCar-X programs on Raspberry Pi 5.

## Service File Location
The service file is located at: `/home/mw/picar-x/picar-x.service`

## Service File Configuration
```ini
[Unit]
Description=PiCar-X Service
After=network.target gpio.target i2c.target basic.target time-sync.target
Wants=network.target gpio.target i2c.target
Requires=basic.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/mw/picar-x
ExecStartPre=/bin/sleep 10
ExecStart=/usr/bin/python3 /home/mw/picar-x/m1/poll_buttons.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Key Features
- Waits for network, GPIO, and I2C to be ready
- Runs as root (needed for GPIO access)
- 10-second delay before starting
- Auto-restarts on crashes
- 10-second delay between restart attempts

## Installation Steps
1. Copy service file to systemd:
```bash
sudo cp /home/mw/picar-x/picar-x.service /etc/systemd/system/
```

2. Reload systemd daemon:
```bash
sudo systemctl daemon-reload
```

3. Enable service for autostart:
```bash
sudo systemctl enable picar-x.service
```

4. Start the service:
```bash
sudo systemctl start picar-x.service
```

## Useful Commands
- Check service status:
```bash
sudo systemctl status picar-x.service
```

- Stop the service:
```bash
sudo systemctl stop picar-x.service
```

- Disable autostart:
```bash
sudo systemctl disable picar-x.service
```

Created: 2025-02-23
