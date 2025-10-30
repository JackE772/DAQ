import pandas as pd
import os

#cd to the folder where your data is stored
#change name of the input file at the bottom of this script
#run code
#THIS FILTERS OUT ALL TIMES UNDER 200,000 ms TO AVOID SHORT RUNS
dataLabels = [
    "yaw_deg",
    "roll_deg",
    "pitch_deg",
    "ax_b",
    "ay_b",
    "az_b",
    "ax_w",
    "ay_w",
    "vx_imu",
    "vy_imu",
    "x_imu",
    "y_imu",
    "lat",
    "lon",
    "xgps",
    "ygps",
    "vx_gps",
    "vy_gps",
    "x_fused",
    "y_fused",
    "vx_fused",
    "vy_fused",
    "sys_cal",
    "g_cal",
    "a_cal",
    "m_cal",
    "millis"
]

def split_csv_on_time_reset(input_file, output_dir="runs", time_col="time", labels=dataLabels):

    # Create output directory if it doesn’t exist
    os.makedirs(output_dir, exist_ok=True)

    # Read the CSV file
    df = pd.read_csv(input_file)

    if time_col not in df.columns:
        raise ValueError(f"'{time_col}' column not found in {input_file}")

    # Ensure time column is integer (in ms)
    df[time_col] = df[time_col].astype(int)

    # Identify where time resets (previous > current)
    reset_points = [0]
    for i in range(1, len(df)):
        if df[time_col].iloc[i] < df[time_col].iloc[i - 1]:
            reset_points.append(i)
    reset_points.append(len(df))  # include last segment end

    # Split into segments
    segment_count = 0
    for i in range(len(reset_points) - 1):
        start, end = reset_points[i], reset_points[i + 1]
        segment = df.iloc[start:end].reset_index(drop=True)

        # Calculate duration in ms
        duration_ms = segment[time_col].iloc[-1] - segment[time_col].iloc[0]

        # Skip segments shorter than (200000 ms)
        if duration_ms < 300000:
            continue

        if labels:
            segment = label_columns(segment, labels)

        segment_count += 1
        output_path = os.path.join(output_dir, f"output_{segment_count}.csv")
        segment.to_csv(output_path, index=False)
        print(f"Saved: {output_path} ({duration_ms / 1000:.2f} s)")

    if segment_count == 0:
        print("No segments longer than 1 minute found.")

def label_columns(df, labels):
    """
    Rename dataframe columns based on a provided list of labels.
    Skips renaming if the number of labels doesn't match the number of columns.
    """
    if len(labels) != len(df.columns):
        print(f"Label count ({len(labels)}) does not match column count ({len(df.columns)}). Skipping relabeling.")
        return df
    df.columns = labels
    return df

if __name__ == "__main__":
    split_csv_on_time_reset(input_file="datalog.csv", output_dir="runs", time_col="time")