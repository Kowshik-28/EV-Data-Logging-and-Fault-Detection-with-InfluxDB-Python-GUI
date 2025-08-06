import pandas as pd
from datetime import datetime, timedelta
import random
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import os

# --- InfluxDB v2 Connection Details ---
# Fill these in with your InfluxDB Cloud credentials
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com/" 
INFLUXDB_TOKEN = "INFLUXDB_TOKEN"
INFLUXDB_ORG = "INFLUXDB_ORG"
INFLUXDB_BUCKET = "INFLUXDB_BUCKET"

# --- Data Generation Parameters ---
VEHICLE_IDS = ["vehicle_A", "vehicle_B"]
START_TIME = datetime(2025, 8, 5, 0, 0, 0)
END_TIME = datetime(2025, 8, 5, 1, 0, 0)  # Only 1 hour of data

# The measurements expected by your analysis script
MEASUREMENTS = {
    'bms_battery_weather': ['battery_soc', 'battery_highest_temp', 'battery_lowest_temp', 'auxilary_battery_voltage'],
    'bms_battery_health': ['battery_soh', 'battery_adaptive_total_capacity'],
    'bms_cell_values': ['cell_voltage', 'cell_internal_resistance'],
    'bms_fault_and_safety_state': ['high_voltage_isolation_fault', 'weak_cell_fault', 'chrg_limit_enforcement_fault', 'dischrg_limit_enforcement_fault', 'input_power_supply_fault', 'redundant_power_supply_fault'],
    'controller_motor_status_2_FRONT': ['motorcontroller_2_controller_temp', 'motorcontroller_2_motor_temp'],
    'controller_motor_status_1_REAR': ['motorcontroller_1_controller_temp', 'motorcontroller_1_motor_temp', 'motorcontroller_1_distance_travelled'],
    'DC_DC_conv_temperature': ['DC_DC_converter_inner_temperature'],
    'DC_DC_conv_workingstatus': ['working_status'],
    'DC_DC_Conv_OutputCurrent': ['12Vconv_Outputcurrent'],
    'DC_DC_Conv_fault_status': ['Over_temperature_shutdown', 'output_overcurrent_alarm', 'output_overvoltage_alarm', 'input_overvoltage_alarm', 'input_undervoltage_alarm', 'output_shortcircuit_protection', 'internal_fault_alarm', 'communication_fault_alarm'],
    'charger_state_limits': ['chrgr_output_current', 'chrgr_temp', 'chrgr_hardware_error_status', 'chrgr_input_voltage_error_status', 'chrgr_communication_error_status'],
    'EPAS_oe_response_state_limits': ['ECUTemperature']
}

def generate_data():
    """Generates a list of InfluxDB Point objects for multiple measurements and vehicles."""
    points = []
    current_time = START_TIME
    time_increment = timedelta(minutes=5) # Data point every 5 minutes
    last_soc = {vehicle_id: None for vehicle_id in VEHICLE_IDS}

    while current_time < END_TIME:
        for vehicle_id in VEHICLE_IDS:
            for measurement, fields in MEASUREMENTS.items():
                point = Point(measurement).tag("vehicle_id", vehicle_id).time(current_time, WritePrecision.NS)

                for field in fields:
                    if field == 'battery_soc':
                        value = random.uniform(0, 100)
                        # Introduce an issue: drop below 10%
                        if current_time.hour == 10 and random.random() < 0.2:
                            value = random.uniform(5, 9.9)
                        # Introduce another issue: rapid drop
                        if current_time.hour == 12 and current_time.minute == 30 and random.random() < 0.2:
                            prev_soc = last_soc[vehicle_id]
                            if prev_soc is not None:
                                value = max(prev_soc - random.uniform(2, 5), 0)
                        point.field(field, value)
                        last_soc[vehicle_id] = value
                    elif field in ['battery_highest_temp', 'bms_temp', 'motorcontroller_1_controller_temp', 'motorcontroller_2_controller_temp']:
                        value = random.uniform(25, 40)
                        # Introduce an issue: high temperature
                        if current_time.hour == 14 and random.random() < 0.2:
                            value = random.uniform(46, 55)
                        point.field(field, value)
                    elif field in ['battery_lowest_temp', 'motorcontroller_1_motor_temp', 'motorcontroller_2_motor_temp']:
                        value = random.uniform(10, 35)
                        # Introduce an issue: low temperature
                        if current_time.hour == 2 and random.random() < 0.2:
                            value = random.uniform(-5, -0.1)
                        point.field(field, value)
                    elif field == 'cell_voltage':
                        value = random.uniform(3000, 3600) # millivolts
                        # Introduce an issue: low cell voltage
                        if current_time.hour == 8 and random.random() < 0.2:
                            value = random.uniform(2000, 2490)
                        point.field(field, value)
                    elif 'fault' in field or 'error' in field or 'shutdown' in field or 'protection' in field:
                        value = 0
                        # Introduce a random fault
                        if random.random() < 0.005:
                            value = 1
                        point.field(field, value)
                    elif field == 'motorcontroller_1_distance_travelled':
                        # This should be cumulative, but for a single-run generator, we can simulate an increase
                        # A real system would read the last value and increment
                        value = (current_time - START_TIME).total_seconds() / 10 + random.uniform(0, 5)
                        point.field(field, value)
                    else:
                        point.field(field, random.uniform(1, 100)) # Default random value

                points.append(point)
        current_time += time_increment

    return points

def write_points_to_influxdb(points):
    """Writes the list of points to InfluxDB."""
    try:
        with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
            with client.write_api(write_options=SYNCHRONOUS) as write_api:
                write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=points)
        print(f"Successfully wrote {len(points)} points to InfluxDB.")
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")

if __name__ == "__main__":
    if "YOUR_INFLUXDB_CLOUD_URL" in INFLUXDB_URL:
        print("Please update your InfluxDB connection details (URL, Token, Org, Bucket) in the script.")
    else:
        print("Generating data...")
        data_points = generate_data()
        print("Writing data to InfluxDB...")
        write_points_to_influxdb(data_points)
        print("Data push complete.")