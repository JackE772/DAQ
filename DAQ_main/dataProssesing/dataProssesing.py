#prosses the data files on a per run basis
#returns max speed, average speed, total distance, total time, peak g forces, average g forces, number of braking events, number of acceleration events

#yaw_deg,roll_deg
#pitch_deg
#ax_b
#ay_b
#az_b
#ax_w
#ay_w
#vx_imu
#vy_imu
#x_imu
#y_imu
#lat
#lon
#xgps
#ygps
#vx_gps
#vy_gps
#x_fused
#y_fused
#vx_fused
#vy_fused
#sys_cal
#g_cal
#a_cal
#m_cal
#millis

import pandas as pd
import numpy as np

xa_DC_offset = 0.0024662959390967104
ya_DC_offset = 0.03943529025506331
za_dc_offset = 0.24582377444442166

def process_acceleration_data(file_path):

    # Load the CSV file
    df = pd.read_csv(file_path)

    # Ensure required columns are present
    required_columns = ['millis', 'ax_b', 'ay_b', 'az_b']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in {file_path}")

    #apply DC offsets
    df['ax_b'] = df['ax_b'] - xa_DC_offset
    df['ay_b'] = df['ay_b'] - ya_DC_offset
    df['az_b'] = df['az_b'] - za_dc_offset

    # Calculate resultant acceleration
    df['a_res'] = np.sqrt(df['ax_b']**2 + df['ay_b']**2 + df['az_b']**2)

    # Calculate max, average acceleration
    max_acceleration = df['a_res'].max()
    avg_acceleration = df['a_res'].mean()

    # Calculate total time in seconds
    total_time = (df['millis'].iloc[-1] - df['millis'].iloc[0]) / 1000.0  # assuming time is in ms

    return {
        'max_acceleration': max_acceleration,
        'avg_acceleration': avg_acceleration,
        'total_time': total_time
    }


def prosses_velocity_data(file_path):

    # Load the CSV file
    df = pd.read_csv(file_path)

    # Ensure required columns are present
    required_columns = ['millis', 'vx_fused', 'vy_fused']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in {file_path}")

    # Calculate resultant velocity
    df['v_res'] = np.sqrt(df['vx_fused']**2 + df['vy_fused']**2)


    # Calculate max, average velocity
    max_velocity = df['v_res'].max()
    avg_velocity = df['v_res'].mean()

    return {
        'max_velocity': max_velocity,
        'avg_velocity': avg_velocity,
    }

def calc_DC_offsets(file_path):

    # Load the CSV file
    df = pd.read_csv(file_path)

    # Ensure required columns are present
    required_columns = ['ax_b', 'ay_b', 'az_b']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in {file_path}")

    # Calculate DC offsets as the mean of each acceleration axis
    dc_offsets = {
        'ax_b_offset': df['ax_b'].mean(),
        'ay_b_offset': df['ay_b'].mean(),
        'az_b_offset': df['az_b'].mean(),
    }

    return dc_offsets
print(process_acceleration_data("output_1.csv"))