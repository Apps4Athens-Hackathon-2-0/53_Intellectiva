import math
from typing import List
from predict import Predictor 

def generate_optimal_schedule(
    tap_in_data: List[List[int]], 
    tap_out_data: List[List[int]],
    train_capacity: int = 1200,
    congestion_target: float = 0.85,
    min_trains_per_hour: int = 4,   # Absolute floor (15 min wait)
    max_trains_per_hour: int = 24,  # Max frequency (2.5 min wait)
    train_op_cost_weight: int = 3500, # Cost to run 1 train (in passenger-wait-minute equivalents)
    debug: bool = False
) -> str:

    # 1. Define Parameters & Init
    try:
        NUM_STATIONS = len(tap_in_data)
        NUM_HOURS = len(tap_in_data[0])
        
        if (NUM_STATIONS != 27 or NUM_HOURS != 24 or
            len(tap_out_data) != 27 or len(tap_out_data[0]) != 24):
            return "Error: Input data must be 27 (stations) x 24 (hours)."
            
    except (TypeError, IndexError):
        return "Error: Invalid data format. Expected List[List[int]]."

    EFFECTIVE_CAPACITY = train_capacity * congestion_target
    if EFFECTIVE_CAPACITY <= 0:
        return "Error: Effective capacity must be greater than zero."

    schedule_lines = []
    schedule_lines.append("🚇 Optimal Metro Schedule (v5: Multi-Objective Optimization) 🚇")
    schedule_lines.append("=" * 70)
    schedule_lines.append(
        f"Params: Cap={train_capacity}, Target={congestion_target*100:.0f}%, "
        f"Min/Max={min_trains_per_hour}/{max_trains_per_hour}, OpCost={train_op_cost_weight}"
    )
    schedule_lines.append("-" * 70)

    service_hours = [0] + list(range(5, 24))
    
    hourly_trains = [0] * NUM_HOURS
    hourly_peak_load = [0] * NUM_HOURS
    total_trains = 0

    # 2. Iterate through each hour to find required trains
    for h in service_hours:
        
        # Calculate total system demand for this hour (used for Wait Time Cost)
        total_hourly_passengers = sum(tap_in_data[s][h] for s in range(NUM_STATIONS))
        
        # Simulate the train filling up and emptying using a Gravity Model
        # This prevents double-counting by splitting passengers based on remaining stations
        
        peak_A = 0
        current_load_A = 0
        
        # Forward pass (Direction A: Station 0 -> 26)
        for s in range(NUM_STATIONS - 1):
            weight_A = sum(tap_out_data[i][h] for i in range(s + 1, NUM_STATIONS))
            weight_B = sum(tap_out_data[i][h] for i in range(0, s))
            ratio_A = weight_A / (weight_A + weight_B) if (weight_A + weight_B) > 0 else 0.5
            board_A = tap_in_data[s][h] * ratio_A
            
            weight_arr_A = sum(tap_in_data[i][h] for i in range(0, s))
            weight_arr_B = sum(tap_in_data[i][h] for i in range(s + 1, NUM_STATIONS))
            ratio_arr_A = weight_arr_A / (weight_arr_A + weight_arr_B) if (weight_arr_A + weight_arr_B) > 0 else 0.5
            alight_A = tap_out_data[s][h] * ratio_arr_A
            
            current_load_A = max(0, current_load_A + board_A - alight_A)
            if current_load_A > peak_A:
                peak_A = current_load_A
                
        peak_B = 0
        current_load_B = 0
        
        # Backward pass (Direction B: Station 26 -> 0)
        for s in range(NUM_STATIONS - 1, 0, -1):
            weight_A = sum(tap_out_data[i][h] for i in range(s + 1, NUM_STATIONS))
            weight_B = sum(tap_out_data[i][h] for i in range(0, s))
            ratio_B = weight_B / (weight_A + weight_B) if (weight_A + weight_B) > 0 else 0.5
            board_B = tap_in_data[s][h] * ratio_B
            
            weight_arr_A = sum(tap_in_data[i][h] for i in range(0, s))
            weight_arr_B = sum(tap_in_data[i][h] for i in range(s + 1, NUM_STATIONS))
            ratio_arr_B = weight_arr_B / (weight_arr_A + weight_arr_B) if (weight_arr_A + weight_arr_B) > 0 else 0.5
            alight_B = tap_out_data[s][h] * ratio_arr_B
            
            current_load_B = max(0, current_load_B + board_B - alight_B)
            if current_load_B > peak_B:
                peak_B = current_load_B
                
        # The true peak segment load for the hour
        peak_hourly_load = max(peak_A, peak_B)
        hourly_peak_load[h] = peak_hourly_load
        
        # --- MULTI-OBJECTIVE OPTIMIZATION ---
        
        # Constraint 1: Absolute minimum to satisfy the Congestion SLA
        if peak_hourly_load == 0:
            min_required_trains = min_trains_per_hour
        else:
            min_required_trains = math.ceil(peak_hourly_load / EFFECTIVE_CAPACITY)
            
        min_required_trains = max(min_trains_per_hour, min_required_trains)
        
        best_k = min_required_trains
        min_cost = float('inf')
        
        # Iterate over possible frequencies to find the lowest "Cost"
        # Total Cost = (Passenger Wait Time Cost) + (Train Operation Cost)
        for k in range(min_required_trains, max_trains_per_hour + 1):
            if k == 0: continue
            
            # If we send k trains, average wait time is 30/k minutes.
            wait_time_minutes = 30.0 / k
            passenger_wait_cost = total_hourly_passengers * wait_time_minutes
            
            # Running k trains costs k * train_op_cost_weight
            operating_cost = k * train_op_cost_weight
            
            total_cost = passenger_wait_cost + operating_cost
            
            if total_cost < min_cost:
                min_cost = total_cost
                best_k = k
                
        required_trains = best_k
        
        hourly_trains[h] = required_trains
        total_trains += required_trains

    # 4. Final Pass: Format Output String
    if debug:
        schedule_lines.append("\n--- DEBUG MODE (v5: Multi-Objective) ---")
        schedule_lines.append(f"Total Trains Scheduled: {total_trains}")
        schedule_lines.append("-" * 70)
        schedule_lines.append(f"{'Hour':<6} | {'Peak Seg Load':<14} | {'Trains':<6} | Congestion (Load/Cap)")
        schedule_lines.append("-" * 70)
        for h in service_hours:
             final_capacity = hourly_trains[h] * EFFECTIVE_CAPACITY
             congestion = hourly_peak_load[h] / final_capacity if final_capacity > 0 else 0
             schedule_lines.append(f"{h:02d}:00 | {hourly_peak_load[h]:<14.0f} | {hourly_trains[h]:<6} | {congestion:.2f}")
        schedule_lines.append("-" * 70)

    schedule_lines.append(
        f"{'Timeframe':<14} | {'Trains':<7} | {'Headway':<10} | Departure Times (approx.)"
    )
    schedule_lines.append("-" * 70)
        
    for h in range(NUM_HOURS):
        start_time_str = f"{h:02d}:00"
        end_time_str = "00:00" if h == 23 else f"{h+1:02d}:00"
        timeframe_str = f"{start_time_str}-{end_time_str}"
        
        if h not in service_hours:
            line = (f"{timeframe_str:<14} | {'-':<7} | {'-':<10} | --- No Service ---")
        else:
            trains_this_hour = hourly_trains[h]
            if trains_this_hour == 0:
                 line = (f"{timeframe_str:<14} | {'0':<7} | {'-':<10} | --- NO TRAINS ALLOCATED ---")
            else:
                minutes_between_trains = 60.0 / trains_this_hour
                departure_times = []
                for i in range(trains_this_hour):
                    departure_minute = int(i * minutes_between_trains)
                    departure_times.append(f"{h:02d}:{departure_minute:02d}")
                times_str = ", ".join(departure_times)
                line = (f"{timeframe_str:<14} | {trains_this_hour:<7} | "
                        f"{minutes_between_trains:<4.1f} min | {times_str}")
        schedule_lines.append(line)

    return "\n".join(schedule_lines)

if __name__ == "__main__":
    
    pred = Predictor()
    print("Initializing predictor")
    pred.init()

    # Simulate a typical Friday in a normal month with raw weather inputs
    weather = {"temperature": 15.0, "precipitation": 0.0, "cloud_cover": 20.0, "wind_speed": 10.0}

    tap_in = [[pred.predict(station, "2025-10-17", f"{str(hour).zfill(2)}:00", "b", **weather)[0]
     for hour in range(24)]
     for station in range(0, 27)
    ]

    tap_out = [[pred.predict(station, "2025-10-17", f"{str(hour).zfill(2)}:00", "d", **weather)[0]
     for hour in range(24)]
     for station in range(0, 27)
    ]

    # Generate the schedule
    timetable_string = generate_optimal_schedule(
        tap_in, 
        tap_out,
        train_capacity=1200,
        congestion_target=0.85, 
        min_trains_per_hour=4,  
        max_trains_per_hour=24, 
        train_op_cost_weight=3500, # Lower this number for more frequent trains, raise it for fewer
        debug=True
    )
    
    # Print the result
    print(timetable_string)