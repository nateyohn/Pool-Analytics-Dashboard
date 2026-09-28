# Author: Nate Yohn
# Description: Cleans the raw pool data files and exports them as CSVs
#              for use with a Power BI dashboard. No database required —
#              this version reads local Excel files and writes local CSVs.

# ========
# Imports
# ========

import os
import pandas as pd
import numpy as np
import requests
import datetime
from dateutil import parser
from datetime import time
from datetime import date
from pathlib import Path


# ============
# File Paths
# ============

# 1. Resolve the absolute path of the directory containing this script
SCRIPT_DIR = Path(__file__).resolve().parent

# 2. Define the project root (one level up from /scripts)
BASE_DIR = SCRIPT_DIR.parent

# 3. Define directory paths dynamically
RAW_DIR = BASE_DIR / "raw_fake_data"
OUTPUT_DIR = BASE_DIR / "cleaned_data"

# Ensure the output folder exists before the script tries to write to it
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 4. Assign specific file paths
snack_shack_path = RAW_DIR / "Pool Concession Sales.xlsx"
membership_path  = RAW_DIR / "Pool Membership Sales.xlsx"
checkins_path    = RAW_DIR / "Pool Visits.xlsx"


# ==========
# Functions
# ==========

def feels_like(temp, windspeed, humidity):
    '''
    Calculates the feels like temperature based on conditions.

    Parameters:
        temp (float): Temperature in Fahrenheit
        windspeed (float): Wind speed in mph
        humidity (float): Humidity percentage

    Returns:
        float: Feels like temperature in Fahrenheit
    '''
    # Wind chill (cold weather)
    if temp <= 50 and windspeed > 3:
        return (35.74 + (0.6215 * temp) -
                (35.75 * windspeed**0.16) +
                (0.4275 * temp * windspeed**0.16))

    # Heat index (hot weather)
    elif temp >= 80 and humidity >= 40:
        return (-42.379 + (2.04901523 * temp) +
                (10.14333127 * humidity) -
                (0.22475541 * temp * humidity) -
                (0.00683783 * temp**2) -
                (0.05481717 * humidity**2) +
                (0.00122874 * temp**2 * humidity) +
                (0.00085282 * temp * humidity**2) -
                (0.00000199 * temp**2 * humidity**2))

    # Mild weather
    else:
        return temp


def clean_text_columns(df):
    '''
    Cleans all text columns in a dataframe by removing
    whitespace and hidden characters.

    Parameters:
        df (dataframe): The dataframe to clean

    Returns:
        dataframe: Cleaned dataframe
    '''
    for col in df.select_dtypes(include='object').columns:
        # Skip columns that contain time or date values
        if df[col].dropna().apply(lambda x: isinstance(x, (datetime.time, datetime.date))).any():
            continue

        df[col] = (df[col]
                   .str.strip()
                   .str.replace('\t', ' ', regex=False)
                   .str.replace('\n', ' ', regex=False)
                   .str.replace('\r', ' ', regex=False)
                   .str.replace(r'\s+', ' ', regex=True)
                   .str.replace(r'[^\x00-\x7F]', '', regex=True)
                  )

    return df


def format_name(name: str) -> str:
    '''
    Formats a name as 'Firstname Lastname' with proper capitalization.

    Parameters:
        name (str): The name to format
    Returns:
        str: The formatted name
    '''
    if pd.isna(name):
        return name
    return " ".join(part.capitalize() for part in name.strip().split())


def format_time(time_val) -> str:
    '''
    Parse messy/mixed time formats and return a clean 24-hour HH:MM:SS string.

    Parameters:
        time_val: The time value to format
    Returns:
        str: The formatted time string (HH:MM:SS), or None on failure
    '''
    if pd.isna(time_val):
        return None
    # Excel sometimes exports time-of-day as a raw fraction of a day
    # (e.g. 0.547199 == 13:07:59) when the cell isn't formatted as Time.
    if isinstance(time_val, (int, float)) and 0 <= time_val < 1:
        total_seconds = round(time_val * 86400)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    try:
        parsed = parser.parse(str(time_val))
        return parsed.strftime("%H:%M:%S")
    except (ValueError, OverflowError):
        return None


def format_date(date_val) -> date:
    '''
    Parse messy/mixed date formats and return a datetime.date object.

    Parameters:
        date_val: The date value to format
    Returns:
        date: The formatted datetime.date object, or None on failure
    '''
    if pd.isna(date_val):
        return None
    try:
        parsed = parser.parse(str(date_val))
        return parsed.date()
    except (ValueError, OverflowError):
        return None


def generate_date_table(start_date: date, end_date: date) -> pd.DataFrame:
    '''
    Generates a date dimension table for Power BI filtering.
    Each row represents one calendar day with pre-computed
    slicing columns so Power BI can filter all tables from
    a single date slicer.

    Parameters:
        start_date (date): First date to include
        end_date (date): Last date to include
    Returns:
        pd.DataFrame: Date dimension table
    '''
    dates = pd.date_range(start=start_date, end=end_date, freq='D')

    date_df = pd.DataFrame({
        'date':         dates.date,
        'year':         dates.year,
        'quarter':      dates.quarter,
        'month_name':   dates.strftime('%B'),
        'month_num':    dates.month,
        'day_of_week':  dates.strftime('%A'),
        'day_num':      dates.dayofweek,   # 0=Monday, 6=Sunday
        'is_weekend':   dates.dayofweek >= 5
    })

    # Cast int columns explicitly
    date_df['year']      = date_df['year'].astype('Int64')
    date_df['quarter']   = date_df['quarter'].astype('Int64')
    date_df['month_num'] = date_df['month_num'].astype('Int64')
    date_df['day_num']   = date_df['day_num'].astype('Int64')

    # Format date column to match other tables
    date_df['date'] = date_df['date'].apply(format_date)

    return date_df


# ================
# Pipeline
# ================

def run_pipeline():
    print("Running pipeline...")
    print(f"[debug] Current working directory: {os.getcwd()}")
    print(f"[debug] Output will be saved to: {OUTPUT_DIR}")

    # Reads Files
    snack_shack_sales = pd.read_excel(snack_shack_path)
    membership_sales  = pd.read_excel(membership_path)
    checkins          = pd.read_excel(checkins_path)

    # =========
    # Checkins
    # =========

    def _parse_checkin_time(val):
        if pd.isna(val):
            return pd.NaT
        if isinstance(val, (int, float)):
            return pd.Timestamp('1899-12-30') + pd.to_timedelta(val, unit='D')
        return pd.to_datetime(val, errors='coerce')

    checkins['checkin_time'] = checkins['checkin_time'].apply(_parse_checkin_time)

    # Splits checkin_time column to checkin_date & checkin_time
    checkins['checkin_date'] = checkins['checkin_time'].dt.date
    checkins['checkin_time'] = checkins['checkin_time'].dt.time

    # Removes whitespace and hidden characters
    checkins = clean_text_columns(checkins)

    # Fills blank membership types with Unknown
    checkins['member_type'] = checkins['member_type'].replace('', 'Unknown').fillna('Unknown')

    # Formats the name column to be consistent
    checkins['name'] = checkins['name'].apply(format_name)

    # Cast bigint columns
    checkins['acct_id'] = checkins['acct_id'].astype('Int64')

    # Format date and time columns
    checkins['checkin_date'] = checkins['checkin_date'].apply(format_date)
    checkins['checkin_time'] = checkins['checkin_time'].apply(format_time)

    # Extract hour, month, year, day of week for Power BI slicing
    checkins['checkin_hour']        = pd.to_datetime(checkins['checkin_time'], format='%H:%M:%S', errors='coerce').dt.hour.astype('Int64')
    checkins_dt                      = pd.to_datetime(checkins['checkin_date'], errors='coerce')
    checkins['checkin_month']        = checkins_dt.dt.month_name()
    checkins['checkin_month_num']    = checkins_dt.dt.month.astype('Int64')
    checkins['checkin_year']         = checkins_dt.dt.year.astype('Int64')
    checkins['checkin_day_of_week']  = checkins_dt.dt.day_name()

    # Composite key for hourly weather join
    checkins['date_hour'] = checkins['checkin_date'].astype(str) + '_' + checkins['checkin_hour'].astype(str)

    # Assign a simple sequential ID
    checkins.insert(0, 'checkin_id', range(1, len(checkins) + 1))

    # =================
    # Membership Sales
    # =================

    # Drops rows where price is 0
    membership_sales = membership_sales[membership_sales['price'] != 0]

    # Splits created column to created_date & created_time
    membership_sales['created'] = pd.to_datetime(membership_sales['created'], errors='coerce')
    membership_sales['created_date'] = membership_sales['created'].dt.date
    membership_sales['created_time'] = membership_sales['created'].dt.time
    membership_sales = membership_sales.drop(columns=['created'])

    # Splits payment_date column to payment_date_only & payment_time
    membership_sales['payment_date'] = pd.to_datetime(membership_sales['payment_date'], errors='coerce')
    membership_sales['payment_date_only'] = membership_sales['payment_date'].dt.date
    membership_sales['payment_time']      = membership_sales['payment_date'].dt.time
    membership_sales = membership_sales.drop(columns=['payment_date'])

    # Strips title column to just the title
    membership_sales['title'] = membership_sales['title'].str.split(':').str[0]

    # Fill blank categories with the title value
    membership_sales['category'] = membership_sales['category'].fillna(membership_sales['title'])

    # Formats the name column to be consistent
    membership_sales['billing_member_name'] = membership_sales['billing_member_name'].apply(format_name)

    # Removes whitespace and hidden characters
    membership_sales = clean_text_columns(membership_sales)

    # Format date columns
    membership_sales['created_date']      = membership_sales['created_date'].apply(format_date)
    membership_sales['payment_date_only'] = membership_sales['payment_date_only'].apply(format_date)

    # Format time columns
    membership_sales['created_time'] = membership_sales['created_time'].apply(format_time)
    membership_sales['payment_time'] = membership_sales['payment_time'].apply(format_time)

    # Extract hour, month, year, day of week for Power BI slicing
    membership_sales['created_hour']         = pd.to_datetime(membership_sales['created_time'], format='%H:%M:%S', errors='coerce').dt.hour.astype('Int64')
    membership_sales['payment_hour']         = pd.to_datetime(membership_sales['payment_time'], format='%H:%M:%S', errors='coerce').dt.hour.astype('Int64')
    created_dt                                = pd.to_datetime(membership_sales['created_date'], errors='coerce')
    payment_dt                                = pd.to_datetime(membership_sales['payment_date_only'], errors='coerce')
    membership_sales['created_month']        = created_dt.dt.month_name()
    membership_sales['created_month_num']    = created_dt.dt.month.astype('Int64')
    membership_sales['created_year']         = created_dt.dt.year.astype('Int64')
    membership_sales['created_day_of_week']  = created_dt.dt.day_name()
    membership_sales['payment_month']        = payment_dt.dt.month_name()
    membership_sales['payment_month_num']    = payment_dt.dt.month.astype('Int64')
    membership_sales['payment_year']         = payment_dt.dt.year.astype('Int64')
    membership_sales['payment_day_of_week']  = payment_dt.dt.day_name()

    # Cast bigint columns
    membership_sales['order_id']  = membership_sales['order_id'].astype('Int64')
    membership_sales['acct_id']   = membership_sales['acct_id'].astype('Int64')
    membership_sales['quantity']  = membership_sales['quantity'].astype('Int64')

    # Assign a simple sequential ID
    membership_sales.insert(0, 'membership_sale_id', range(1, len(membership_sales) + 1))

    # =================
    # Snack Shack Sales
    # =================

    # Drops unnecessary columns
    dropped_columns = [
        'Time Zone', 'SKU', 'Modifiers Applied', 'Payment ID',
        'Device Name', 'Details', 'Event Type', 'Location', 'Dining Option',
        'Customer ID', 'Customer Name', 'Customer Reference ID', 'Unit', 'Count',
        'GTIN', 'Itemization Type', 'Commission', 'Employee', 'Fulfillment Note',
        'Channel', 'Token', 'Card Brand', 'PAN Suffix', 'Card'
    ]
    snack_shack_sales = snack_shack_sales.drop(columns=dropped_columns, errors='ignore')

    # Formats the time column
    snack_shack_sales['Time'] = snack_shack_sales['Time'].apply(format_time)

    # Corrects missing values in Category column
    category_map = (
        snack_shack_sales.dropna(subset=['Category'])
        .groupby('Item')['Category']
        .first()
        .to_dict()
    )

    snack_shack_sales['Category'] = snack_shack_sales['Category'].fillna(
        snack_shack_sales['Item'].map(category_map)
    )

    # For any items still missing a category, fall back to the item name itself
    snack_shack_sales['Category'] = snack_shack_sales['Category'].fillna(snack_shack_sales['Item'])

    # If Price Point Name is NaN, use the Category value
    snack_shack_sales['Price Point Name'] = snack_shack_sales['Price Point Name'].fillna(
        snack_shack_sales['Category']
    )

    # Format date column
    snack_shack_sales['Date'] = snack_shack_sales['Date'].apply(format_date)

    # Extract hour, month, year, day of week for Power BI slicing
    snack_shack_sales['Hour']         = pd.to_datetime(snack_shack_sales['Time'], format='%H:%M:%S', errors='coerce').dt.hour.astype('Int64')
    snack_dt                           = pd.to_datetime(snack_shack_sales['Date'], errors='coerce')
    snack_shack_sales['Month']        = snack_dt.dt.month_name()
    snack_shack_sales['Month_Num']    = snack_dt.dt.month.astype('Int64')
    snack_shack_sales['Year']         = snack_dt.dt.year.astype('Int64')
    snack_shack_sales['Day_Of_Week']  = snack_dt.dt.day_name()

    # Converts negative sales values (refunds) to their positive equivalent
    for sales_col in ('Gross Sales', 'Net Sales'):
        if sales_col in snack_shack_sales.columns:
            snack_shack_sales[sales_col] = snack_shack_sales[sales_col].abs()

    # Cast bigint columns
    snack_shack_sales['Qty']       = snack_shack_sales['Qty'].astype('Int64')
    snack_shack_sales['Discounts'] = snack_shack_sales['Discounts'].round().astype('Int64')
    snack_shack_sales['Tax']       = snack_shack_sales['Tax'].round().astype('Int64')

    # Fills NaN notes with blank
    snack_shack_sales['Notes'] = snack_shack_sales['Notes'].fillna('')

    # Lowercase + replace spaces with underscores
    snack_shack_sales.columns = snack_shack_sales.columns.str.lower().str.replace(" ", "_")

    # Composite key for hourly weather join
    snack_shack_sales['date_hour'] = snack_shack_sales['date'].astype(str) + '_' + snack_shack_sales['hour'].astype(str)

    # Assign a simple sequential ID
    snack_shack_sales.insert(0, 'sss_id', range(1, len(snack_shack_sales) + 1))

    # ========
    # Weather
    # ========

    # Determine date range across all 3 datasets
    all_dates = []
    if not checkins.empty:
        all_dates.append(checkins['checkin_date'].min())
    if not membership_sales.empty:
        all_dates.append(membership_sales['created_date'].min())
    if not snack_shack_sales.empty:
        all_dates.append(snack_shack_sales['date'].min())

    weather_start = min(d for d in all_dates if d is not None) if all_dates else None
    weather_end   = datetime.date.today()

    if weather_start and weather_start <= weather_end:
        url = 'https://archive-api.open-meteo.com/v1/archive'

        parameters = {
            'latitude': 40.1529,
            'longitude': -76.6024,
            'start_date': weather_start.strftime('%Y-%m-%d'),
            'end_date': weather_end.strftime('%Y-%m-%d'),
            'hourly': ['temperature_2m', 'precipitation',
                       'windspeed_10m', 'relativehumidity_2m',
                       'cloudcover', 'weathercode'],
            'timezone': 'America/New_York',
            'temperature_unit': 'fahrenheit',
            'windspeed_unit': 'mph',
            'precipitation_unit': 'inch'
        }

        response = requests.get(url, params=parameters)
        data = response.json()

        weather_df = pd.DataFrame({
            'datetime':      data['hourly']['time'],
            'temperature':   data['hourly']['temperature_2m'],
            'precipitation': data['hourly']['precipitation'],
            'windspeed':     data['hourly']['windspeed_10m'],
            'humidity':      data['hourly']['relativehumidity_2m'],
            'cloud_cover':   data['hourly']['cloudcover'],
            'weather_code':  data['hourly']['weathercode']
        })

        # Splits datetime into date and time
        weather_df['datetime'] = pd.to_datetime(weather_df['datetime'])
        weather_df['date'] = weather_df['datetime'].dt.date
        weather_df['time'] = weather_df['datetime'].dt.time
        weather_df.drop(columns=['datetime'], inplace=True)

        # Feels like temperature
        weather_df['feels_like'] = weather_df.apply(
            lambda row: feels_like(row['temperature'], row['windspeed'], row['humidity']),
            axis=1
        ).round(2)

        # Weather code descriptions
        weather_codes = {
            0: 'Clear Sky', 1: 'Mainly Clear', 2: 'Partly Cloudy', 3: 'Overcast',
            45: 'Fog', 48: 'Icy Fog', 51: 'Light Drizzle', 53: 'Moderate Drizzle',
            55: 'Heavy Drizzle', 61: 'Light Rain', 63: 'Moderate Rain', 65: 'Heavy Rain',
            71: 'Light Snow', 73: 'Moderate Snow', 75: 'Heavy Snow', 77: 'Snow Grains',
            80: 'Light Showers', 81: 'Moderate Showers', 82: 'Heavy Showers',
            85: 'Light Snow Showers', 86: 'Heavy Snow Showers', 95: 'Thunderstorm',
            96: 'Thunderstorm with Hail', 99: 'Heavy Thunderstorm with Hail'
        }

        weather_df['weather_description'] = weather_df['weather_code'].map(weather_codes)

        # Format date and time
        weather_df['date'] = weather_df['date'].apply(format_date)
        weather_df['time'] = weather_df['time'].apply(format_time)

        # Extract hour, month, year for Power BI slicing
        weather_df['hour']      = pd.to_datetime(weather_df['time'], format='%H:%M:%S', errors='coerce').dt.hour.astype('Int64')
        weather_dt               = pd.to_datetime(weather_df['date'], errors='coerce')
        weather_df['month']     = weather_dt.dt.month_name()
        weather_df['month_num'] = weather_dt.dt.month.astype('Int64')
        weather_df['year']      = weather_dt.dt.year.astype('Int64')

        # Composite key for hourly fact table joins
        weather_df['date_hour'] = weather_df['date'].astype(str) + '_' + weather_df['hour'].astype(str)

        # Cast bigint columns
        weather_df['humidity']     = weather_df['humidity'].astype('Int64')
        weather_df['cloud_cover']  = weather_df['cloud_cover'].astype('Int64')
        weather_df['weather_code'] = weather_df['weather_code'].astype('Int64')

        # Assign a simple sequential ID
        weather_df.insert(0, 'weather_id', range(1, len(weather_df) + 1))
    else:
        weather_df = pd.DataFrame()
        print("  [weather] No date range found. Skipping weather fetch.")

    # ============
    # Date Table
    # ============

    all_min_dates = []
    if not checkins.empty:
        all_min_dates.append(pd.to_datetime(checkins['checkin_date'].dropna()).min().date())
    if not membership_sales.empty:
        all_min_dates.append(pd.to_datetime(membership_sales['created_date'].dropna()).min().date())
    if not snack_shack_sales.empty:
        all_min_dates.append(pd.to_datetime(snack_shack_sales['date'].dropna()).min().date())

    date_start = min(all_min_dates) if all_min_dates else datetime.date(2023, 5, 1)
    date_end   = datetime.date.today()

    date_table = generate_date_table(date_start, date_end)

    # ================
    # Export to CSV
    # ================

    snack_shack_sales.to_csv(OUTPUT_DIR / 'snack_shack_sales_cleaned.csv', index=False)
    membership_sales.to_csv(OUTPUT_DIR / 'membership_sales_cleaned.csv', index=False)
    checkins.to_csv(OUTPUT_DIR / 'checkins_cleaned.csv', index=False)
    date_table.to_csv(OUTPUT_DIR / 'date_table_cleaned.csv', index=False)
    if not weather_df.empty:
        weather_df.to_csv(OUTPUT_DIR / 'weather_cleaned.csv', index=False)

    print(f"All files cleaned and saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    run_pipeline()