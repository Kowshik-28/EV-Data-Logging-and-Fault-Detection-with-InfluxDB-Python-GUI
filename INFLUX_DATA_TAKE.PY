import tkinter as tk
from tkinter import scrolledtext, messagebox, END, W, E, N, S
from tkinter import ttk # Import ttk for Notebook widget
import pandas as pd
import pytz
from datetime import datetime, timedelta
import threading # To prevent GUI from freezing during data fetching
from tkcalendar import DateEntry # For date picker functionality

# InfluxDB v2 Client imports
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS # Only if you need to write data


# --- Global Constants and Color Palette ---
VEHICLE_IDS_FILE = "saved_vehicle_ids.txt"
SECRET_CODE = "1234" # Define the 4-digit code to unlock settings

# Modern, clean color palette
COLOR_PRIMARY_BG = "#E0FFFF" # Light Cyan - main window background
COLOR_SECONDARY_BG = "#F0F8FF" # Alice Blue - frame backgrounds
COLOR_TEXT = "#333333"       # Dark Gray - general text
COLOR_BUTTON_BG = "#4682B4"  # Steel Blue - button background
COLOR_BUTTON_HOVER = "#589ACF" # Lighter blue for hover effect
COLOR_BUTTON_FG = "#FFFFFF"  # White - button text
COLOR_HIGHLIGHT = "#ADD8E6"  # Light Blue - for active elements if needed
COLOR_ENTRY_BG = "#FFFFFF"   # White - entry fields background
COLOR_TEXT_AREA_BG = "#FFFFE0" # Light Yellow - for scrolled text backgrounds

# --- InfluxDB v2 Connection Details ---
# Fill these in with your InfluxDB Cloud credentials
INFLUXDB_URL = "https://us-east-1-1.aws.cloud2.influxdata.com/"
INFLUXDB_TOKEN = "INFLUXDB_TOKEN" # Replace with your actual token
INFLUXDB_ORG = "INFLUXDB_ORG"
INFLUXDB_BUCKET = "INFLUXDB_BUCKET" # IMPORTANT: Replace with your actual bucket name, e.g., "my_vehicle_data"


# --- Utility Functions ---

def date_range(start_date, end_date):
    """Generates a list of dates between start_date and end_date (inclusive)."""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    while start <= end:
        yield start.strftime('%Y-%m-%d')
        start += timedelta(days=1)


# --- New InfluxDB v2 Data Fetching Functions ---

def fetch_data_for_analysis(vehicle_id, date_obj, timezone_str, measurement):
    """
    Fetches data for a specific vehicle, date, and measurement from InfluxDB v2
    using the Flux query language.
    Returns a Pandas DataFrame.
    """
    try:
        # Convert date_obj to start and end of day in the specified timezone
        tz = pytz.timezone(timezone_str)
        start_dt_localized = tz.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 0))
        end_dt_localized = tz.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59)) # End of day

        start_time_flux = start_dt_localized.isoformat()
        end_time_flux = end_dt_localized.isoformat()

        with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
            query_api = client.query_api()

            # This query fetches all fields for the given measurement, vehicle_id, and time range
            # and pivots them into columns.
            query = f'''
            from(bucket: "{INFLUXDB_BUCKET}")
              |> range(start: {start_time_flux}, stop: {end_time_flux})
              |> filter(fn: (r) => r._measurement == "{measurement}") 
              |> filter(fn: (r) => r.vehicle_id == "{vehicle_id}")
              |> pivot(rowKey:["_time", "vehicle_id"], columnKey: ["_field"], valueColumn: "_value")
            '''
            
            df = query_api.query_data_frame(org=INFLUXDB_ORG, query=query)
            
            if not df.empty:
                # Rename _time to time for consistency with your existing detector functions
                df = df.rename(columns={'_time': 'time'})
                # Convert 'time' column to datetime objects without timezone info for detector functions
                df['time'] = pd.to_datetime(df['time']).dt.tz_localize(None)
                return df
            
            return pd.DataFrame() # Return an empty DataFrame if no data is found

    except Exception as e:
        print(f"Error fetching data from InfluxDB: {e}")
        return pd.DataFrame()


def get_unique_vehicle_ids_v2(start_date_obj, end_date_obj, timezone_str):
    """
    Fetches unique vehicle_ids that have data within the specified time range using Flux.
    """
    try:
        tz = pytz.timezone(timezone_str)
        start_dt_localized = tz.localize(datetime(start_date_obj.year, start_date_obj.month, start_date_obj.day, 0, 0, 0))
        end_dt_localized = tz.localize(datetime(end_date_obj.year, end_date_obj.month, end_date_obj.day, 23, 59, 59))

        start_time_flux = start_dt_localized.isoformat()
        end_time_flux = end_dt_localized.isoformat()

        with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
            query_api = client.query_api()
            query = f'''
            from(bucket: "{INFLUXDB_BUCKET}")
              |> range(start: {start_time_flux}, stop: {end_time_flux})
              |> keep(columns: ["vehicle_id"])
              |> distinct(column: "vehicle_id")
            '''
            result = query_api.query(org=INFLUXDB_ORG, query=query)
            vehicle_ids = set()
            for table in result:
                for record in table.records:
                    vehicle_ids.add(record.values.get("vehicle_id"))
            return sorted(list(vehicle_ids))
    except Exception as e:
        print(f"Error fetching unique vehicle IDs with Flux: {e}")
        return []

def get_vehicle_distance_v2(vehicle_id, start_date_obj, end_date_obj, timezone_str):
    """
    Fetches the total distance traveled for a specific vehicle within a time range using Flux.
    """
    try:
        tz = pytz.timezone(timezone_str)
        start_dt_localized = tz.localize(datetime(start_date_obj.year, start_date_obj.month, start_date_obj.day, 0, 0, 0))
        end_dt_localized = tz.localize(datetime(end_date_obj.year, end_date_obj.month, end_date_obj.day, 23, 59, 59))

        start_time_flux = start_dt_localized.isoformat()
        end_time_flux = end_dt_localized.isoformat()

        with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
            query_api = client.query_api()
            # Simplified Flux query to get first and last distance values
            query = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: {start_time_flux}, stop: {end_time_flux})
  |> filter(fn: (r) => r._measurement == "controller_motor_status_1_REAR" and r._field == "motorcontroller_1_distance_travelled" and r.vehicle_id == "{vehicle_id}")
  |> sort(columns: ["_time"])
  |> last()
  |> union(tables: [
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: {start_time_flux}, stop: {end_time_flux})
      |> filter(fn: (r) => r._measurement == "controller_motor_status_1_REAR" and r._field == "motorcontroller_1_distance_travelled" and r.vehicle_id == "{vehicle_id}")
      |> sort(columns: ["_time"])
      |> first()
  ])
  |> yield(name: "distance_points")
'''
            df = query_api.query_data_frame(org=INFLUXDB_ORG, query=query)
            
            if not df.empty and '_value' in df.columns:
                # Ensure we have at least two points (first and last)
                if len(df['_value']) >= 2:
                    first_dist = df['_value'].min() # Get the minimum value, assuming it's the first
                    last_dist = df['_value'].max()  # Get the maximum value, assuming it's the last
                    return last_dist - first_dist
                elif len(df['_value']) == 1:
                    # If only one point, distance is 0 or not calculable for range
                    return 0.0
        return None
    except Exception as e:
        print(f"Error fetching distance with Flux: {e}")
        return None


def prepare_dataframe(df, timezone):
    """
    Preprocesses the DataFrame by converting 'time' column to datetime objects,
    localizing to the specified timezone, removing timezone info, and sorting.
    """
    if df.empty:
        return df
    try:
        # 'time' column should already be datetime from fetch_data_for_analysis and tz-localized=None
        # So we just ensure it's sorted
        df = df.sort_values('time').reset_index(drop=True)
    except Exception as e:
        print(f"Error preparing dataframe: {e}") # Keep console print for debugging internal issues
        return pd.DataFrame() # Return empty on error during preparation

    return df

# --- Detector Functions (These remain largely the same, but ensure they use the 'time' column correctly) ---

def detect_soc_issues(df, timezone):
    if df.empty or 'battery_soc' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    condition1 = df['battery_soc'] < 10
    df['soc_diff'] = df['battery_soc'].diff().abs()
    df['time_diff'] = df['time'].diff().dt.total_seconds()
    condition2 = (df['soc_diff'] >= 2) & (df['time_diff'] <= 60)
    return df[condition1 | condition2].drop(columns=['soc_diff', 'time_diff'], errors='ignore')

def detect_hightemp_issues(df, timezone):
    if df.empty or 'battery_highest_temp' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['battery_highest_temp'] > 45]

def detect_lowtemp_issues(df, timezone):
    if df.empty or 'battery_lowest_temp' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['battery_lowest_temp'] <= 0]

def detect_auxilary_battery_voltage(df, timezone):
    if df.empty or 'auxilary_battery_voltage' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['auxilary_battery_voltage'] < 11]

# Note: 'bms_temp' is not in your MEASUREMENTS list for data generation.
# If you intend to use it, you'll need to add it to your data generation script.
def detect_bmstemp_issues(df, timezone):
    if df.empty or 'bms_temp' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['bms_temp'] > 45]

def detect_soh_issues(df, timezone):
    if df.empty or 'battery_soh' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['battery_soh'] < 60]

def detect_battery_adaptive_total_capacity(df, timezone):
    if df.empty or 'battery_adaptive_total_capacity' not in df.columns:
        return pd.DataFrame()
    
    df = prepare_dataframe(df, timezone)
    
    condition_low_capacity = df['battery_adaptive_total_capacity'] < 160

    df['capacity_change'] = df['battery_adaptive_total_capacity'].diff()
    df['time_diff'] = df['time'].diff().dt.total_seconds()

    condition_drop_value = (df['capacity_change'] <= -5) & (df['capacity_change'] >= -15)
    condition_change_time = df['time_diff'] <= 60

    condition_rapid_drop = condition_drop_value & condition_change_time

    return df[condition_low_capacity | condition_rapid_drop].drop(columns=['capacity_change', 'time_diff'], errors='ignore')

def detect_low_cell_voltage(df, timezone):
    if df.empty or 'cell_voltage' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    df['cell_voltage_v'] = df['cell_voltage'] * 0.001
    return df[(df['cell_voltage_v'] < 2.5) | (df['cell_voltage_v'] > 3.66)] 

def detect_cell_internal_resistance(df, timezone):
    if df.empty or 'cell_internal_resistance' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['cell_internal_resistance'] > 0.45]

def detect_true_iso_faults(df, timezone):
    if df.empty or 'high_voltage_isolation_fault' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['high_voltage_isolation_fault'] == 1]

def detect_true_weakcell_faults(df, timezone):
    if df.empty or 'weak_cell_fault' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['weak_cell_fault'] == 1]

def detect_true_chrg_limit_enforcement_faults(df, timezone):
    if df.empty or 'chrg_limit_enforcement_fault' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['chrg_limit_enforcement_fault'] == 1]

def detect_true_dischrg_limit_enforcement_faults(df, timezone):
    if df.empty or 'dischrg_limit_enforcement_fault' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['dischrg_limit_enforcement_fault'] == 1]

def detect_input_power_supply_faults(df, timezone):
    if df.empty or 'input_power_supply_fault' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['input_power_supply_fault'] == 1]

def detect_redundant_power_supply_faults(df, timezone):
    if df.empty or 'redundant_power_supply_fault' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['redundant_power_supply_fault'] == 1]

def detect_cm2_Heatsink_temp(df, timezone):
    if df.empty or 'motorcontroller_2_controller_temp' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[(df['motorcontroller_2_controller_temp'] >= 70) | (df['motorcontroller_2_controller_temp'] < 0)]

def detect_cm2_Motor_temp(df, timezone):
    if df.empty or 'motorcontroller_2_motor_temp' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[(df['motorcontroller_2_motor_temp'] >= 110) | (df['motorcontroller_2_motor_temp'] < 0)]

def detect_cm1_Heatsink_temp(df, timezone):
    if df.empty or 'motorcontroller_1_controller_temp' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[(df['motorcontroller_1_controller_temp'] >= 70) | (df['motorcontroller_1_controller_temp'] < 0)]

def detect_cm1_Motor_temp(df, timezone):
    if df.empty or 'motorcontroller_1_motor_temp' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[(df['motorcontroller_1_motor_temp'] >= 110) | (df['motorcontroller_1_motor_temp'] < 0)]

def detect_DC_DC_conv_temperature(df, timezone):
    if df.empty or 'DC_DC_converter_inner_temperature' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[(df['DC_DC_converter_inner_temperature'] >= 80) | (df['DC_DC_converter_inner_temperature'] < 0)]

def detect_working_status(df, timezone):
    if df.empty or 'working_status' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['working_status'] == 1]

def detect_DC_DC_current(df, timezone):
    """
    Detects DC-DC output current issues: sustained current > 60A for at least 120 seconds.
    """
    if df.empty or '12Vconv_Outputcurrent' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    df['above_60A'] = df['12Vconv_Outputcurrent'] > 60
    df['time_diff'] = df['time'].diff().dt.total_seconds()
    df['group'] = (df['above_60A'] != df['above_60A'].shift()).cumsum()
    sustained_groups = df[df['above_60A']].groupby('group')
    valid_rows = []
    for _, group in sustained_groups:
        duration = (group['time'].iloc[-1] - group['time'].iloc[0]).total_seconds()
        if duration >= 120:
            valid_rows.append(group)
    if valid_rows:
        result_df = pd.concat(valid_rows)
        return result_df.drop(columns=['above_60A', 'group', 'time_diff'], errors='ignore')
    else:
        return pd.DataFrame(columns=df.columns)
    
def detect_Over_temperature_shutdown(df, timezone):
    if df.empty or 'Over_temperature_shutdown' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['Over_temperature_shutdown'] == 1]

def detect_output_overcurrent_alarm(df, timezone):
    if df.empty or 'output_overcurrent_alarm' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['output_overcurrent_alarm'] == 1]

def detect_output_overvoltage_alarm(df, timezone):
    if df.empty or 'output_overvoltage_alarm' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['output_overvoltage_alarm'] == 1]

def detect_input_overvoltage_alarm(df, timezone):
    if df.empty or 'input_overvoltage_alarm' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['input_overvoltage_alarm'] == 1]

def detect_input_undervoltage_alarm(df, timezone):
    if df.empty or 'input_undervoltage_alarm' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['input_undervoltage_alarm'] == 1]

def detect_output_shortcircuit_protection(df, timezone):
    if df.empty or 'output_shortcircuit_protection' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['output_shortcircuit_protection'] == 1]

def detect_internal_fault_alarm(df, timezone):
    if df.empty or 'internal_fault_alarm' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['internal_fault_alarm'] == 1]

def detect_communication_fault_alarm(df, timezone):
    if df.empty or 'communication_fault_alarm' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['communication_fault_alarm'] == 1]

def detect_chrgr_output_current(df, timezone):
    if df.empty or 'chrgr_output_current' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['chrgr_output_current'] >= 32]

def detect_chrgr_temp(df, timezone):
    if df.empty or 'chrgr_temp' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['chrgr_temp'] >= 60]

def detect_chrgr_hardware_error_status(df, timezone):
    if df.empty or 'chrgr_hardware_error_status' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['chrgr_hardware_error_status'] == 1]

def detect_chrgr_input_voltage_error_status(df, timezone):
    if df.empty or 'chrgr_input_voltage_error_status' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['chrgr_input_voltage_error_status'] == 1]

def detect_chrgr_communication_error_status(df, timezone):
    if df.empty or 'chrgr_communication_error_status' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[df['chrgr_communication_error_status'] == 1]

def detect_ECU_temperature(df, timezone):
    if df.empty or 'ECUTemperature' not in df.columns: return pd.DataFrame()
    df = prepare_dataframe(df, timezone)
    return df[(df['ECUTemperature'] >= 70) | (df['ECUTemperature'] < 0)]

class InfluxApp:
    def __init__(self, master):
        self.master = master
        master.title("InfluxDB Vehicle Issue Detector")
        master.configure(bg=COLOR_PRIMARY_BG) # Apply primary background to main window

        # Configure grid weights for responsive layout
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=0) # Left panel (controls) fixed width
        master.grid_columnconfigure(1, weight=1) # Right panel (results) expands

        # --- Left Panel: InfluxDB Connection & Analysis Parameters ---
        self.left_panel = tk.Frame(master, padx=10, pady=10, bg=COLOR_PRIMARY_BG)
        self.left_panel.grid(row=0, column=0, sticky="nsew")

        # Configure ttk styles for a modern look
        self.style = ttk.Style()
        self.style.theme_use('clam') # Use 'clam' for more customization options
        self.style.configure('TLabelFrame', background=COLOR_SECONDARY_BG, foreground=COLOR_TEXT, relief="groove")
        self.style.configure('TLabel', background=COLOR_SECONDARY_BG, foreground=COLOR_TEXT)
        self.style.configure('TButton', background=COLOR_BUTTON_BG, foreground=COLOR_BUTTON_FG, font=('Arial', 10, 'bold'))
        self.style.map('TButton', background=[('active', COLOR_HIGHLIGHT)])
        self.style.configure('TCombobox', fieldbackground=COLOR_ENTRY_BG, background=COLOR_BUTTON_BG, foreground=COLOR_TEXT)
        self.style.map('TCombobox', fieldbackground=[('readonly', COLOR_ENTRY_BG)])
        self.style.configure('TNotebook', background=COLOR_SECONDARY_BG, borderwidth=0)
        self.style.configure('TNotebook.Tab', background=COLOR_HIGHLIGHT, foreground=COLOR_TEXT, padding=[10, 5])
        self.style.map('TNotebook.Tab', background=[('selected', COLOR_BUTTON_BG)], foreground=[('selected', COLOR_BUTTON_FG)])
        self.style.configure('TFrame', background=COLOR_SECONDARY_BG)

        # Password entry for settings - New section
        self.password_frame = ttk.LabelFrame(self.left_panel, text="Unlock Settings") 
        self.password_frame.pack(fill="x", pady=5)

        tk.Label(self.password_frame, text="Enter 4-digit code:", bg=COLOR_SECONDARY_BG, fg=COLOR_TEXT).grid(row=0, column=0, sticky="w", pady=2)
        self.password_entry_field = tk.Entry(self.password_frame, width=15, show="*", bg=COLOR_ENTRY_BG, fg=COLOR_TEXT)
        self.password_entry_field.grid(row=0, column=1, pady=2, padx=5, sticky="ew")

        self.unlock_button = ttk.Button(self.password_frame, text="Unlock", command=self.check_password)
        self.unlock_button.grid(row=0, column=2, pady=2, padx=5)

        # InfluxDB Connection Settings - This frame will now be hidden by default and removed
        # as connection details are hardcoded in global constants for InfluxDB v2
        # self.conn_frame = ttk.LabelFrame(self.left_panel, text="InfluxDB Connection Settings") 
        # ... (removed old connection widgets) ...


        # Analysis Parameters - ALWAYS packed (no initial pack_forget)
        self.param_frame = ttk.LabelFrame(self.left_panel, text="Analysis Parameters")
        self.param_frame.pack(fill="x", pady=5) # This frame is always visible

        tk.Label(self.param_frame, text="Add Vehicle ID:", bg=COLOR_SECONDARY_BG, fg=COLOR_TEXT).grid(row=0, column=0, sticky="w", pady=2)
        self.single_vehicle_id_combobox = ttk.Combobox(self.param_frame, width=30, state="normal")
        self.single_vehicle_id_combobox.grid(row=0, column=1, pady=2, padx=5, sticky="ew")
        
        self.add_vehicle_button = ttk.Button(self.param_frame, text="Add", command=self.add_vehicle_id_to_list)
        self.add_vehicle_button.grid(row=0, column=2, pady=2, padx=5)
        
        tk.Label(self.param_frame, text="Selected Vehicles:", bg=COLOR_SECONDARY_BG, fg=COLOR_TEXT).grid(row=1, column=0, sticky="nw", pady=2)
        self.selected_vehicles_listbox = tk.Listbox(self.param_frame, height=5, width=40, selectmode=tk.EXTENDED, bg=COLOR_ENTRY_BG, fg=COLOR_TEXT)
        self.selected_vehicles_listbox.grid(row=1, column=1, columnspan=2, pady=2, padx=5, sticky="nsew")
        self.param_frame.grid_rowconfigure(1, weight=1) # Allow listbox to expand vertically
        
        self.remove_vehicle_button = ttk.Button(self.param_frame, text="Remove Selected", command=self.remove_selected_vehicle_ids)
        self.remove_vehicle_button.grid(row=2, column=1, columnspan=2, pady=5, sticky="ew")

        self.delete_all_button = ttk.Button(self.param_frame, text="Delete All", command=self.delete_all_vehicle_ids)
        self.delete_all_button.grid(row=2, column=0, pady=5, padx=5, sticky="ew")

        # New button to fetch active vehicles
        self.fetch_active_button = ttk.Button(self.param_frame, text="Fetch Active Vehicles", command=self.fetch_active_vehicles_threaded)
        self.fetch_active_button.grid(row=3, column=1, columnspan=2, pady=5, sticky="ew") # Placed below Add/Remove

        # Load saved vehicle IDs into the history combobox and selected list
        self.load_and_populate_vehicle_ids()

        tk.Label(self.param_frame, text="Start Date (YYYY-MM-DD):", bg=COLOR_SECONDARY_BG, fg=COLOR_TEXT).grid(row=4, column=0, sticky="w", pady=2) # Row adjusted
        self.start_date_entry = DateEntry(self.param_frame, width=27, background=COLOR_BUTTON_BG, foreground=COLOR_BUTTON_FG, borderwidth=2, date_pattern='yyyy-mm-dd')
        self.start_date_entry.grid(row=4, column=1, pady=2, padx=5, sticky="ew")
        self.start_date_entry.set_date(datetime(2025, 8, 5)) # Default value to match data generation

        tk.Label(self.param_frame, text="End Date (YYYY-MM-DD):", bg=COLOR_SECONDARY_BG, fg=COLOR_TEXT).grid(row=5, column=0, sticky="w", pady=2) # Row adjusted
        self.end_date_entry = DateEntry(self.param_frame, width=27, background=COLOR_BUTTON_BG, foreground=COLOR_BUTTON_FG, borderwidth=2, date_pattern='yyyy-mm-dd')
        self.end_date_entry.grid(row=5, column=1, pady=2, padx=5, sticky="ew")
        self.end_date_entry.set_date(datetime(2025, 8, 5)) # Default value to match data generation

        tk.Label(self.param_frame, text="Timezone:", bg=COLOR_SECONDARY_BG, fg=COLOR_TEXT).grid(row=6, column=0, sticky="w", pady=2) # Row adjusted
        self.timezone_combobox = ttk.Combobox(self.param_frame, width=27, state="readonly") # Readonly for selection only
        self.timezone_combobox.grid(row=6, column=1, pady=2, padx=5, sticky="ew")
        self.timezone_combobox['values'] = sorted(pytz.all_timezones) # Populate with all timezones
        self.timezone_combobox.set('Asia/Kolkata') # Default value

        self.run_button = ttk.Button(self.left_panel, text="Run Analysis", command=self.run_analysis_threaded)
        self.run_button.pack(pady=10) # This button is always visible

        # --- Right Panel: Results Display (split into two) ---
        self.right_panel = tk.Frame(master, padx=10, pady=10, bg=COLOR_PRIMARY_BG)
        self.right_panel.grid(row=0, column=1, sticky="nsew")
        self.right_panel.grid_rowconfigure(0, weight=1) # Log frame expands
        self.right_panel.grid_rowconfigure(1, weight=3) # Notebook frame expands more
        self.right_panel.grid_columnconfigure(0, weight=1)

        self.log_frame = ttk.LabelFrame(self.right_panel, text="Processing Logs") # Use ttk.LabelFrame
        self.log_frame.grid(row=0, column=0, sticky="nsew", pady=5)
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, width=80, height=10, bg=COLOR_TEXT_AREA_BG, fg=COLOR_TEXT)
        self.log_text.pack(expand=True, fill="both")
        self.log_text.insert(END, "General processing messages will appear here.\n")

        # Use a ttk.Notebook for tabs instead of a single issues detail frame
        self.notebook = ttk.Notebook(self.right_panel)
        self.notebook.grid(row=1, column=0, sticky="nsew", pady=5)


        # Define all detectors and their primary columns for display
        self.detectors = [
            ('bms_battery_weather', detect_soc_issues, 'bms_battery_weather_soc', ['battery_soc']),
            ('bms_battery_weather', detect_hightemp_issues, 'bms_battery_weather_high_temp', ['battery_highest_temp']),
            ('bms_battery_weather', detect_lowtemp_issues, 'bms_battery_weather_low_temp', ['battery_lowest_temp']),
            ('bms_battery_weather', detect_auxilary_battery_voltage, 'bms_auxilary_battery_voltage', ['auxilary_battery_voltage']),
            ('bms_battery_weather', detect_bmstemp_issues, 'bms_battery_weather_bms_temp', ['bms_temp']),
            ('bms_battery_health', detect_soh_issues, 'bms_battery_health_soh', ['battery_soh']),
            ('bms_battery_health', detect_battery_adaptive_total_capacity, 'bms_adaptive_total_capacity', ['battery_adaptive_total_capacity']),
            ('bms_cell_values', detect_low_cell_voltage, 'bms_cell_values_low_voltage', ['cell_voltage_v']), # Display converted voltage
            ('bms_cell_values', detect_cell_internal_resistance, 'bms_cell_internal_resistance', ['cell_internal_resistance']),
            ('bms_fault_and_safety_state', detect_true_iso_faults, 'bms_iso_fault', ['high_voltage_isolation_fault']),
            ('bms_fault_and_safety_state', detect_true_weakcell_faults, 'bms_weak_cell_fault', ['weak_cell_fault']),
            ('bms_fault_and_safety_state', detect_true_chrg_limit_enforcement_faults, 'bms_chrg_limit_enforce_fault', ['chrg_limit_enforcement_fault']),
            ('bms_fault_and_safety_state', detect_true_dischrg_limit_enforcement_faults, 'bms_dischrg_limit_enforcement_fault', ['dischrg_limit_enforcement_fault']),
            ('bms_fault_and_safety_state', detect_input_power_supply_faults, 'bms_input_power_supply_fault', ['input_power_supply_fault']),
            ('bms_fault_and_safety_state', detect_redundant_power_supply_faults, 'bms_redundant_power_supply_fault', ['redundant_power_supply_fault']),
            ('controller_motor_status_2_FRONT', detect_cm2_Heatsink_temp, 'cm2_front_heatsink_temp', ['motorcontroller_2_controller_temp']),
            ('controller_motor_status_2_FRONT', detect_cm2_Motor_temp, 'cm2_front_motor_temp', ['motorcontroller_2_motor_temp']),
            ('controller_motor_status_1_REAR', detect_cm1_Heatsink_temp, 'cm1_rear_heatsink_temp', ['motorcontroller_1_controller_temp']),
            ('controller_motor_status_1_REAR', detect_cm1_Motor_temp, 'cm1_rear_motor_temp', ['motorcontroller_1_motor_temp']),
            ('DC_DC_conv_temperature', detect_DC_DC_conv_temperature, 'DC_DC_inner_temperature', ['DC_DC_converter_inner_temperature']),
            ('DC_DC_conv_workingstatus', detect_working_status, 'DC_DC_working_status', ['working_status']),
            ('DC_DC_Conv_OutputCurrent', detect_DC_DC_current, 'DC_DC_current_sustained', ['12Vconv_Outputcurrent']),
            ('DC_DC_Conv_fault_status', detect_Over_temperature_shutdown, 'DC_DC_over_temp_shutdown', ['Over_temperature_shutdown']),
            ('DC_DC_Conv_fault_status', detect_output_overcurrent_alarm, 'DC_DC_output_overcurrent_alarm', ['output_overcurrent_alarm']),
            ('DC_DC_Conv_fault_status', detect_output_overvoltage_alarm, 'DC_DC_output_overvoltage_alarm', ['output_overvoltage_alarm']),
            ('DC_DC_Conv_fault_status', detect_input_overvoltage_alarm, 'DC_DC_input_overvoltage_alarm', ['input_overvoltage_alarm']),
            ('DC_DC_Conv_fault_status', detect_input_undervoltage_alarm, 'DC_DC_input_undervoltage_alarm', ['input_undervoltage_alarm']),
            ('DC_DC_Conv_fault_status', detect_output_shortcircuit_protection, 'DC_DC_output_shortcircuit_prot', ['output_shortcircuit_protection']),
            ('DC_DC_Conv_fault_status', detect_internal_fault_alarm, 'DC_DC_internal_fault_alarm', ['internal_fault_alarm']),
            # ('DC_DC_Conv_fault_status', detect_communication_fault_alarm, 'DC_DC_communication_fault_alarm', ['communication_fault_alarm']),
            ('charger_state_limits', detect_chrgr_output_current, 'charger_output_current_high', ['chrgr_output_current']),
            ('charger_state_limits', detect_chrgr_temp, 'charger_chrgr_temp_high', ['chrgr_temp']),
            ('charger_state_limits', detect_chrgr_hardware_error_status, 'charger_chrgr_hardware_error', ['chrgr_hardware_error_status']),
            ('charger_state_limits', detect_chrgr_input_voltage_error_status, 'charger_chrgr_input_voltage_error', ['chrgr_input_voltage_error_status']),
            ('charger_state_limits', detect_chrgr_communication_error_status, 'charger_chrgr_communication_error', ['chrgr_communication_error_status']),
            ('EPAS_oe_response_state_limits', detect_ECU_temperature, 'EPAS_Temperature', ['ECUTemperature'])
        ]
        
    def load_vehicle_ids(self):
        """Loads vehicle IDs from a file."""
        try:
            with open(VEHICLE_IDS_FILE, 'r') as f:
                ids = [line.strip() for line in f if line.strip()]
                return sorted(list(set(ids))) # Return unique and sorted
        except FileNotFoundError:
            return []

    def save_vehicle_ids(self, vehicle_ids):
        """Saves vehicle IDs to a file."""
        # Ensure unique IDs before saving
        unique_ids = sorted(list(set(vehicle_ids)))
        try:
            with open(VEHICLE_IDS_FILE, 'w') as f:
                for vid in unique_ids:
                    f.write(vid + '\n')
        except IOError as e:
            self.log_message(f"Error saving vehicle IDs: {e}")

    def load_and_populate_vehicle_ids(self):
        """Loads vehicle IDs and populates both the combobox and the listbox."""
        loaded_ids = self.load_vehicle_ids()
        self.single_vehicle_id_combobox['values'] = loaded_ids
        self.selected_vehicles_listbox.delete(0, END) # Clear existing listbox entries
        for vid in loaded_ids: # Initially populate the listbox with all saved IDs
            self.selected_vehicles_listbox.insert(END, vid)

    def add_vehicle_id_to_list(self):
        """Adds the vehicle ID from the combobox to the selected vehicles list."""
        new_id = self.single_vehicle_id_combobox.get().strip()
        if new_id and new_id not in self.selected_vehicles_listbox.get(0, END):
            self.selected_vehicles_listbox.insert(END, new_id)
            self.single_vehicle_id_combobox.set("") # Clear combobox after adding
            # Add to saved list if new
            current_saved_ids = self.load_vehicle_ids()
            if new_id not in current_saved_ids:
                current_saved_ids.append(new_id)
                self.save_vehicle_ids(current_saved_ids)
                self.single_vehicle_id_combobox['values'] = sorted(list(set(current_saved_ids))) # Update combobox values

    def remove_selected_vehicle_ids(self):
        """Removes selected vehicle IDs from the listbox."""
        selected_indices = self.selected_vehicles_listbox.curselection()
        for index in selected_indices[::-1]: # Iterate backwards to avoid index issues
            self.selected_vehicles_listbox.delete(index)

    def delete_all_vehicle_ids(self):
        """Deletes all vehicle IDs from the listbox and saved file."""
        self.selected_vehicles_listbox.delete(0, END)
        self.save_vehicle_ids([]) # Clear saved file
        self.single_vehicle_id_combobox['values'] = [] # Clear combobox values

    def log_message(self, message):
        """Appends a message to the general log text area."""
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END) # Scroll to the end

    def check_password(self):
        """Checks the entered password to unlock connection settings."""
        entered_password = self.password_entry_field.get()
        if entered_password == SECRET_CODE:
            self.password_frame.pack_forget() # Hide the password input frame
            self.log_message("Settings unlocked. InfluxDB connection details are configured in the script's global constants.")
        else:
            messagebox.showerror("Authentication Failed", "Incorrect 4-digit code.")
            self.password_entry_field.delete(0, END) # Clear the field

    def fetch_active_vehicles_threaded(self):
        """Starts fetching active vehicles in a separate thread."""
        self.log_text.delete(1.0, END) # Clear previous log results
        self.log_message("Fetching active vehicles... Please wait.")
        self.fetch_active_button.config(state=tk.DISABLED)
        self.run_button.config(state=tk.DISABLED)

        fetch_thread = threading.Thread(target=self._fetch_active_vehicles_logic)
        fetch_thread.start()

    def _fetch_active_vehicles_logic(self):
        """Logic for fetching active vehicles from InfluxDB."""
        try:
            # Removed config dictionary as it's no longer used for InfluxDB v2
            start_date_obj = self.start_date_entry.get_date()
            end_date_obj = self.end_date_entry.get_date()
            timezone_str = self.timezone_combobox.get()

            # Use the new get_unique_vehicle_ids_v2 function
            active_vehicle_ids = get_unique_vehicle_ids_v2(
                start_date_obj, end_date_obj, timezone_str
            )
            
            self.master.after(0, lambda: self._update_vehicle_lists(active_vehicle_ids))
            self.master.after(0, lambda: self.log_message(f"Found {len(active_vehicle_ids)} active vehicles."))

        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Error", f"Failed to fetch active vehicles: {e}"))
            self.master.after(0, lambda: self.log_message(f"Error fetching active vehicles: {e}"))
        finally:
            self.master.after(0, lambda: self.fetch_active_button.config(state=tk.NORMAL))
            self.master.after(0, lambda: self.run_button.config(state=tk.NORMAL))

    def _update_vehicle_lists(self, new_ids):
        """Updates the selected vehicles listbox and combobox with new IDs."""
        current_listbox_ids = list(self.selected_vehicles_listbox.get(0, END))
        for vid in new_ids:
            if vid not in current_listbox_ids:
                self.selected_vehicles_listbox.insert(END, vid)
        
        # Also ensure the saved file and combobox values are updated
        all_ids_in_listbox = list(self.selected_vehicles_listbox.get(0, END))
        self.save_vehicle_ids(all_ids_in_listbox)
        self.single_vehicle_id_combobox['values'] = sorted(list(set(self.load_vehicle_ids())))


    def run_analysis_threaded(self):
        """Starts the analysis in a separate thread to keep the GUI responsive."""
        self.log_text.delete(1.0, END) # Clear previous log results
        
        # Clear existing tabs
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)

        self.log_message("Starting analysis... Please wait.")
        self.run_button.config(state=tk.DISABLED) # Disable button during analysis
        self.fetch_active_button.config(state=tk.DISABLED) # Also disable fetch button

        analysis_thread = threading.Thread(target=self._run_analysis_logic)
        analysis_thread.start()

    def _run_analysis_logic(self):
        """The main logic for fetching and analyzing data, run in a separate thread."""
        try:
            # Removed config dictionary as it's no longer used for InfluxDB v2
            
            # Get vehicle IDs from the selected listbox
            vehicle_ids = list(self.selected_vehicles_listbox.get(0, END))
            
            # Save the current list of vehicles being analyzed to history for future use
            self.save_vehicle_ids(vehicle_ids) 
            # Update combobox values on the main thread after saving
            self.master.after(0, lambda: self.single_vehicle_id_combobox.config(values=self.load_vehicle_ids()))


            start_date_obj = self.start_date_entry.get_date()
            end_date_obj = self.end_date_entry.get_date()

            start_date_str = start_date_obj.strftime('%Y-%m-%d')
            end_date_str = end_date_obj.strftime('%Y-%m-%d')

            timezone = self.timezone_combobox.get()

            # Input validation (basic)
            if not vehicle_ids:
                messagebox.showerror("Input Error", "Please add at least one Vehicle ID to the 'Selected Vehicles' list.")
                self.master.after(0, lambda: self.run_button.config(state=tk.NORMAL))
                self.master.after(0, lambda: self.fetch_active_button.config(state=tk.NORMAL))
                return
            if not start_date_str or not end_date_str:
                messagebox.showerror("Input Error", "Please select Start and End Dates.")
                self.master.after(0, lambda: self.run_button.config(state=tk.NORMAL))
                self.master.after(0, lambda: self.fetch_active_button.config(state=tk.NORMAL))
                return
            if start_date_obj > end_date_obj:
                messagebox.showerror("Input Error", "Start Date cannot be after End Date.")
                self.master.after(0, lambda: self.run_button.config(state=tk.NORMAL))
                self.master.after(0, lambda: self.fetch_active_button.config(state=tk.NORMAL))
                return
            try:
                pytz.timezone(timezone)
            except pytz.UnknownTimeZoneError:
                messagebox.showerror("Input Error", f"Unknown timezone: {timezone}")
                self.master.after(0, lambda: self.run_button.config(state=tk.NORMAL))
                self.master.after(0, lambda: self.fetch_active_button.config(state=tk.NORMAL))
                return

            # Removed client = create_influxdb_client(**config)
            dates_list = list(date_range(start_date_str, end_date_str))

            # Dictionary to store all detected issues, grouped by vehicle_id
            vehicle_issues_map = {vid: [] for vid in vehicle_ids} 
            vehicle_distances = {} # To store calculated distances

            for vehicle_id in vehicle_ids:
                self.log_message(f"\n======== Processing Vehicle: {vehicle_id} ========")
                
                # Fetch and store vehicle distance using the new v2 function
                distance = get_vehicle_distance_v2(vehicle_id, start_date_obj, end_date_obj, timezone)
                vehicle_distances[vehicle_id] = distance
                if distance is not None:
                    self.log_message(f"Total Distance for {vehicle_id}: {distance:.2f} KM")
                else:
                    self.log_message(f"Could not determine total distance for {vehicle_id}.")

                for date_str in dates_list: # Iterate through date strings
                    # Convert date_str back to date_obj for fetch_data_for_analysis
                    current_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date() 
                    self.log_message(f"\n🔍 Processing date: {date_str} for vehicle {vehicle_id}")
                    
                    current_date_issues_for_vehicle = [] 

                    for measurement, detector_func, issue_type_name, display_columns in self.detectors:
                        # Use the new fetch_data_for_analysis function
                        # Pass current_date_obj for both start and end date since we're processing day by day
                        df = fetch_data_for_analysis(vehicle_id, current_date_obj, timezone, measurement) 
                        filtered_df = detector_func(df, timezone)
                        
                        if not filtered_df.empty:
                            current_date_issues_for_vehicle.append({
                                'vehicle_id': vehicle_id,
                                'date': date_str, # Keep date_str for display
                                'measurement': measurement,
                                'issue_type': issue_type_name,
                                'data': filtered_df,
                                'display_cols': display_columns 
                            })
                            self.log_message(f"✅ {issue_type_name} issues detected for {date_str} for vehicle {vehicle_id}")

                    if current_date_issues_for_vehicle:
                        vehicle_issues_map[vehicle_id].extend(current_date_issues_for_vehicle)
                        self.log_message(f"✅ Issues found on {date_str} for vehicle {vehicle_id}.")
                    else:
                        self.log_message(f"✅ No issues found on {date_str} for vehicle {vehicle_id}.")

            # --- Create and Populate Tabs for Each Vehicle ---
            any_issues_found_overall = False
            for vehicle_id, issues_for_this_vehicle in vehicle_issues_map.items():
                if issues_for_this_vehicle:
                    any_issues_found_overall = True
                
                # Create a new frame for this vehicle's main tab
                main_vehicle_tab_frame = ttk.Frame(self.notebook)
                self.notebook.add(main_vehicle_tab_frame, text=vehicle_id)

                # Display total distance at the top of the main vehicle tab
                distance_text = f"Total Distance Traveled (KM): "
                if vehicle_distances.get(vehicle_id) is not None:
                    distance_text += f"{vehicle_distances[vehicle_id]:.2f} KM"
                else:
                    distance_text += "N/A"
                
                distance_label = tk.Label(main_vehicle_tab_frame, text=distance_text, 
                                        bg=COLOR_SECONDARY_BG, fg=COLOR_TEXT, 
                                        font=('Arial', 12, 'bold'), pady=5)
                distance_label.pack(fill="x", padx=5, pady=5)


                # Create a sub-notebook within this main vehicle tab
                sub_notebook = ttk.Notebook(main_vehicle_tab_frame)
                sub_notebook.pack(expand=True, fill="both", padx=5, pady=5)
                
                # Group issues by issue_type for sub-tabs
                issues_by_type = {}
                for issue in issues_for_this_vehicle:
                    issue_type = issue['issue_type']
                    if issue_type not in issues_by_type:
                        issues_by_type[issue_type] = []
                    issues_by_type[issue_type].append(issue)

                if not issues_by_type: # If no issues, add a "No Issues" sub-tab
                    no_issues_sub_tab = ttk.Frame(sub_notebook)
                    sub_notebook.add(no_issues_sub_tab, text="No Issues")
                    no_issues_text = scrolledtext.ScrolledText(no_issues_sub_tab, wrap=tk.WORD, width=100, height=30, bg=COLOR_TEXT_AREA_BG, fg=COLOR_TEXT)
                    no_issues_text.pack(expand=True, fill="both", padx=5, pady=5)
                    no_issues_text.insert(END, "\n\nNo specific issues detected for this vehicle within the selected date range.")
                else:
                    for issue_type, issues_list in issues_by_type.items():
                        # Create a sub-tab for each issue type
                        sub_tab_frame = ttk.Frame(sub_notebook)
                        sub_notebook.add(sub_tab_frame, text=issue_type)

                        # Add a ScrolledText widget to this sub-tab
                        sub_text_widget = scrolledtext.ScrolledText(sub_tab_frame, wrap=tk.WORD, width=100, height=30, bg=COLOR_TEXT_AREA_BG, fg=COLOR_TEXT)
                        sub_text_widget.pack(expand=True, fill="both", padx=5, pady=5)
                        
                        sub_text_widget.insert(END, f"======== {issue_type} Issues for {vehicle_id} ========\n")
                        for issue in issues_list:
                            sub_text_widget.insert(END, f"\n--- Date: {issue['date']} ---\n")
                            
                            # Select only 'time' and the specified display columns
                            cols_to_display = ['time'] + [col for col in issue['display_cols'] if col in issue['data'].columns]
                            
                            # Add specific derived columns for certain issue types if they exist
                            if issue['issue_type'] == 'bms_battery_weather_soc':
                                if 'soc_diff' in issue['data'].columns:
                                    cols_to_display.append('soc_diff')
                                if 'time_diff' in issue['data'].columns:
                                    cols_to_display.append('time_diff')
                            elif issue['issue_type'] == 'DC_DC_current_sustained':
                                if 'time_diff' in issue['data'].columns:
                                    cols_to_display.append('time_diff')

                            # Ensure no duplicate columns and only include columns actually present in the DataFrame
                            final_cols_to_display = []
                            seen_cols = set()
                            for col in cols_to_display:
                                if col not in seen_cols and col in issue['data'].columns: # Check existence in df
                                    final_cols_to_display.append(col)
                                    seen_cols.add(col)

                            if not final_cols_to_display: # Fallback if no relevant columns found
                                sub_text_widget.insert(END, "No specific columns to display, showing all:\n")
                                sub_text_widget.insert(END, issue['data'].to_string(index=False) + "\n")
                            else:
                                sub_text_widget.insert(END, issue['data'][final_cols_to_display].to_string(index=False) + "\n")
                            sub_text_widget.insert(END, "-" * 50 + "\n")

            if not any_issues_found_overall:
                # If no issues at all were found across all vehicles, add a general tab or message
                no_issues_tab = ttk.Frame(self.notebook)
                self.notebook.add(no_issues_tab, text="No Issues (Overall)")
                no_issues_text = scrolledtext.ScrolledText(no_issues_tab, wrap=tk.WORD, width=100, height=30, bg=COLOR_TEXT_AREA_BG, fg=COLOR_TEXT)
                no_issues_text.pack(expand=True, fill="both", padx=5, pady=5)
                no_issues_text.insert(END, "\n\nNo issues detected across all specified vehicles and dates.")
                self.log_message("\n\nAnalysis complete. No issues detected across all specified vehicles and dates.")
            else:
                self.log_message("\n\nAnalysis complete. Check vehicle tabs for detailed issues.")


        except Exception as e:
            messagebox.showerror("Error during analysis", f"An unexpected error occurred: {e}")
            self.log_message(f"\nError: {e}") # Log error to general log as well
        finally:
            self.master.after(0, lambda: self.run_button.config(state=tk.NORMAL)) # Ensure button is re-enabled on main thread
            self.master.after(0, lambda: self.fetch_active_button.config(state=tk.NORMAL)) # Re-enable fetch button


if __name__ == '__main__':
    root = tk.Tk()
    app = InfluxApp(root)
    root.mainloop()
