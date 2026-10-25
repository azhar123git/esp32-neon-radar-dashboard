# esp32-neon-radar-dashboard
Real-time ESP32 ultrasonic radar dashboard built with Python, featuring a glowing radar sweep, live distance detection, scan progress, sensor status, and a futuristic neon HUD interface.
ESP32 Ultrasonic Radar

A real-time radar-style visualization using an ESP32, an ultrasonic distance sensor, a servo motor, and Python.

Components
ESP32 development board
HC-SR04 ultrasonic sensor
Servo motor
USB data cable
Computer with Python installed
Features
Scans from 0° to 180°
Measures distance up to 200 cm
Filters multiple ultrasonic readings
Displays detected objects on a live Python radar screen
Software
Arduino IDE
Python 3
PySerial
Matplotlib
NumPy
How to Run
Upload the Arduino sketch to the ESP32.
Install the Python libraries: python -m pip install pyserial matplotlib numpy
Set the correct serial port in radar.py.
Close the Arduino Serial Monitor.
Run python radar.py.
Author

Azhar
