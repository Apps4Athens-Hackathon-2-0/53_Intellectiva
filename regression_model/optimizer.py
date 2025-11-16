import math
from typing import List

# This line is in your file, so I include it for context.
from predict import Predictor 

def generate_optimal_schedule(
    tap_in_data: List[List[int]], 
    tap_out_data: List[List[int]],
    train_capacity: int = 1200,
    congestion_target: float = 0.85,
    min_trains_per_hour: int = 3,
    max_trains_per_hour: int = 20,
    max_trains_per_day: int = 170,
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
    schedule_lines.append("🚇 Optimal Metro Schedule (v3: Daily Budget Allocation) 🚇")
    schedule_lines.append("=" * 70)
    schedule_lines.append(
        f"Params: Train Capacity={train_capacity}, "
        f"Congestion Target={congestion_target*100:.0f}%, "
        f"Hourly Min/Max={min_trains_per_hour}/{max_trains_per_hour}"
    )
    schedule_lines.append(f"DAILY BUDGET: {max_trains_per_day} Total Trains")
    schedule_lines.append("-" * 70)

    # Store the calculated "Total Demand" (worst of peak load or system load) for each hour
    hourly_demand = [0] * NUM_HOURS
    # Service runs for 20 hours: 00:00 (hour 0) and 05:00-23:00 (hours 5-23)
    service_hours = [0] + list(range(5, 24))

    # 2. First Pass: Calculate Total Demand per Hour
    for h in service_hours:
        # Metric 1: Peak Segment Load
        load_outbound = [0] * NUM_STATIONS
        load_outbound[0] = tap_in_data[0][h]
        for s in range(1, NUM_STATIONS):
            load = load_outbound[s-1] - tap_out_data[s][h] + tap_in_data[s][h]
            load_outbound[s] = max(0, load) 
        peak_out = max(load_outbound)

        load_inbound = [0] * NUM_STATIONS
        load_inbound[NUM_STATIONS - 1] = tap_in_data[NUM_STATIONS - 1][h]
        for s in range(NUM_STATIONS - 2, -1, -1):
            load = load_inbound[s+1] - tap_out_data[s][h] + tap_in_data[s][h]
            load_inbound[s] = max(0, load)
            
        peak_in = max(load_inbound)
        
        peak_hourly_load = max(peak_out, peak_in)

        # Metric 2: Total System Demand
        total_tap_in = 0
        for s in range(NUM_STATIONS):
            total_tap_in += tap_in_data[s][h]
        
        # The total "demand" for this hour is the worse of the two bottlenecks
        hourly_demand[h] = max(peak_hourly_load, total_tap_in)

    # 3. Second Pass: Allocate Daily Train Budget
    
    schedule = [0] * NUM_HOURS # This will hold the final train count for each hour
    total_trains_allocated = 0
    
    # A. Handle potential conflict between min_trains_per_hour and max_trains_per_day
    # If the budget is too small, we must use a smaller, achievable minimum.
    num_service_hours = len(service_hours)
    min_trains_this_run = min(min_trains_per_hour, max_trains_per_day // num_service_hours)
    
    if min_trains_this_run < min_trains_per_hour and debug:
         schedule_lines.append(f"WARNING: max_trains_per_day ({max_trains_per_day}) is too low to meet")
         schedule_lines.append(f"         min_trains_per_hour ({min_trains_per_hour}). Using reduced min of {min_trains_this_run}.")

    # B. Allocate the "floor" (minimum trains) to all service hours
    for h in service_hours:
        schedule[h] = min_trains_this_run
        total_trains_allocated += min_trains_this_run
        
    # C. Iteratively allocate the "remaining" trains to the most congested hours
    remaining_trains = max_trains_per_day - total_trains_allocated
    
    for _ in range(remaining_trains):
        best_h = -1
        max_congestion_metric = -1
        
        for h in service_hours:
            # Skip this hour if it's already at its hourly max
            if schedule[h] >= max_trains_per_hour:
                continue
                
            # Find the hour with the worst "congestion"
            # Congestion = Demand / Capacity
            current_capacity = schedule[h] * EFFECTIVE_CAPACITY
            
            if current_capacity == 0:
                # Any hour with 0 trains has "infinite" congestion
                congestion_metric = float('inf')
            else:
                congestion_metric = hourly_demand[h] / current_capacity

            if congestion_metric > max_congestion_metric:
                max_congestion_metric = congestion_metric
                best_h = h
                
        if best_h == -1:
            # This happens if all hours are at their max_trains_per_hour
            # We have leftover trains in our budget but nowhere to put them
            if debug:
                unused_trains = max_trains_per_day - total_trains_allocated
                schedule_lines.append(f"NOTE: All hours at max. {unused_trains} daily trains unused.")
            break 
            
        # Allocate one train to the worst-congested hour
        schedule[best_h] += 1
        total_trains_allocated += 1

    # 4. Final Pass: Format Output String
    if debug:
        schedule_lines.append("\n--- DEBUG MODE (v3: Daily Budget Allocation) ---")
        schedule_lines.append(f"Total Daily Budget: {max_trains_per_day}")
        schedule_lines.append(f"Base Allocation: {total_trains_allocated - remaining_trains} trains ({num_service_hours} hrs * {min_trains_this_run} min)")
        schedule_lines.append(f"Prioritized Allocation: {remaining_trains} trains")
        schedule_lines.append(f"Total Allocated: {total_trains_allocated}")
        schedule_lines.append("-" * 70)
        schedule_lines.append(f"{'Hour':<6} | {'Total Demand':<12} | {'Final Trains':<6} | Congestion (Demand/Cap)")
        schedule_lines.append("-" * 70)
        for h in service_hours:
             final_capacity = schedule[h] * EFFECTIVE_CAPACITY
             congestion = hourly_demand[h] / final_capacity if final_capacity > 0 else float('inf')
             schedule_lines.append(f"{h:02d}:00 | {hourly_demand[h]:<12.0f} | {schedule[h]:<6} | {congestion:.2f}")
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
            trains_this_hour = schedule[h]
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

    # Simulate a friday
    tap_in = [[pred.predict(station, "2025-11-21", f"{str(hour).zfill(2)}:00", "b", 90)[0]
     for hour in range(24)]
     for station in range(0, 27)
    ]

    tap_out = [[pred.predict(station, "2025-11-21", f"{str(hour).zfill(2)}:00", "d", 90)[0]
     for hour in range(24)]
     for station in range(0, 27)
    ]

    # 2. Generate the schedule
    timetable_string = generate_optimal_schedule(
        tap_in, 
        tap_out,
        train_capacity=1200, # average OASA train capacity
        congestion_target=0.9, # target optimization (0.9 * initial_congestion)
        min_trains_per_hour=4, # minimum trains (at least 4 per hour)
        max_trains_per_hour=20, # max trains 
        max_trains_per_day=170, # oasa based
        debug=True
    )
    
    # 3. Print the result
    print(timetable_string)