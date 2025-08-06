# EV-Data-Logging-and-Fault-Detection-with-InfluxDB-Python-GUI

Built an end-to-end vehicle data simulator and analyzer using InfluxDB and Python. Simulated EV telemetry like SOC, temperature, faults, and pushed it to InfluxDB. Created a Tkinter GUI to retrieve, analyze, and detect issues like low SOC, high temp, and charger faults.

## 🚗 Project Overview

This project demonstrates how to:

1. Simulate vehicle data and push it to InfluxDB v2.0
2. Retrieve and analyze the data using a Tkinter-based GUI for detecting battery and system-level anomalies in electric vehicles.

## 🧰 Components

### 1. `create_influx_data.py`
- Simulates 1 hour of vehicle data (2 vehicles).
- Writes data to InfluxDB.
- Includes SOC, temperature, SOH, cell voltages, faults, charger and motor stats.

### 2. `INFLUX_DATA_TAKE.py`
- Tkinter GUI for:
  - Selecting vehicles and time range
  - Fetching data from InfluxDB using Flux
  - Detecting issues using predefined rules
  - Displaying results in categorized tabs

## 💡 Features
- InfluxDB v2.0 + Flux integration
- GUI with date range, timezone, and vehicle selection
- Detectors for battery, charger, motor faults
- Real-time logging and issue display

## 📦 Installation
```bash
pip install influxdb-client tk tkcalendar pandas pytz
```

## 🔧 Configuration
Update these in both files:
```python
INFLUXDB_URL = "https://your-cloud-url"
INFLUXDB_TOKEN = "your-token"
INFLUXDB_ORG = "your-org"
INFLUXDB_BUCKET = "your-bucket"
```

## 🚀 Usage
### Generate Data
```bash
python create_influx_data.py
```
### Run GUI
```bash
python INFLUX_DATA_TAKE.py
```

## 📹 Video Demo
<a href="https://www.youtube.com/"> Watch how the data is pushed, retrieved, and analyzed.</a>

## 🧑‍💻 Author
**Kowshik Kancharla** — Connect on <a href="https://www.linkedin.com/in/kowshik-kancharla-596794204/">[LinkedIn_ kowshik-kancharla]</a>
