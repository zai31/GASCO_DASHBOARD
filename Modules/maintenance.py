from pulp import *
import pandas as pd
import os

def load_compressors_from_excel():
    """Load compressor data from Excel file"""
    df = pd.read_excel("Data/Compressor_Data.xlsx", engine='openpyxl')
    compressors = {}
    
    for _, row in df.iterrows():
        compressor_id = row['Compressor ID']
        current_hrs = row['Current Hours']
        compressors[compressor_id] = {'current_hrs': current_hrs}
    
    return compressors

def calculate_next_maintenance_dates(compressor_id, current_hours, assigned_hours, hours_per_day=24):
    """Calculate next maintenance dates based on current hours and assigned hours"""
    from datetime import datetime, timedelta
    
    # Find current position in 21k cycle
    cycle_position = current_hours % total_cycle_hours
    
    # Find next maintenance thresholds
    next_maintenances = []
    
    # Check each maintenance point in the cycle
    for i, maint_hours in enumerate(cumulative_hours_for_maint):
        if cycle_position < maint_hours:
            # This maintenance is still ahead in current cycle
            hours_until_maint = maint_hours - cycle_position
            maint_type = maintenance_types[i]
            
            # Calculate date (only add first upcoming maintenance)
            days_until = hours_until_maint / hours_per_day
            maint_date = datetime.now() + timedelta(days=days_until)
            
            next_maintenances.append({
                'type': maint_type,
                'hours_until': hours_until_maint,
                'date': maint_date.strftime('%Y-%m-%d'),
                'total_hours_at_maint': current_hours + hours_until_maint
            })
            break  # Only get the next immediate maintenance
    
    # If we've passed all maintenances in current cycle, add next cycle's first maintenance
    if not next_maintenances:
        hours_until_cycle_end = total_cycle_hours - cycle_position
        hours_until_first_maint = hours_until_cycle_end + cumulative_hours_for_maint[0]
        days_until = hours_until_first_maint / hours_per_day
        maint_date = datetime.now() + timedelta(days=days_until)
        
        next_maintenances.append({
            'type': maintenance_types[0],
            'hours_until': hours_until_first_maint,
            'date': maint_date.strftime('%Y-%m-%d'),
            'total_hours_at_maint': current_hours + hours_until_first_maint
        })
    
    return next_maintenances

# Load compressors from Excel or use fallback
compressors = load_compressors_from_excel()
maintenance_types = [3000, 6000, 3000, 6000, 3000, 6000, 21000]
cumulative_hours_for_maint = [3000, 6000, 9000, 12000, 15000, 18000, 21000]
total_cycle_hours = 21000
total_annual_hours = 17520
costs = {3000: 1.0, 6000: 1.8, 21000: 6.0}

# --- True MIP model: exact step costs via binaries ---
def build_event_schedule_for_compressor(comp_name, comp_data, total_horizon_hours,
                                        maintenance_types, cumulative_hours_for_maint, costs):
    """
    Build a list of (threshold_hours_from_now, maint_type) events the compressor would hit
    as it runs forward from its current state, respecting the cyclic sequence.
    """
    events = []
    # hours until next maintenance from current position within the 21k cycle
    r = comp_data['hrs_until_next_maint']  # 0..3000
    seq_idx = comp_data['sequence_index']  # index in maintenance_types for the *next* maintenance

    # First event (if you run at least r hours)
    if r > 0 and r <= total_horizon_hours:
        events.append((r, maintenance_types[seq_idx]))
    # Subsequent events every 3000 hours
    remaining = total_horizon_hours - r
    step_idx = (seq_idx + 1) % len(maintenance_types)
    t = r + 3000
    while t <= total_horizon_hours:
        events.append((t, maintenance_types[step_idx]))
        step_idx = (step_idx + 1) % len(maintenance_types)
        t += 3000
    return events  # list of (threshold, type)
def debug_event_schedule(c, H_var, y_dict, events):
    print(f"\n--- Diagnostics for Compressor {c} ---")
    print("Assigned Hours =", value(H_var[c]))
    for i, (thr, mtype) in enumerate(events):
        yval = value(y_dict[(c, i)])
        print(f"  event {i}: thr={thr}, type={mtype}, y={yval}")


def solve_true_min_cost_mip():
    prob = LpProblem("True_Minimize_Maintenance_Cost", LpMinimize)

    # Decision: total run hours per compressor (continuous)
    H = {c: LpVariable(f"H_{c}", lowBound=0, upBound=total_annual_hours, cat=LpContinuous)
         for c in compressors.keys()}

    # Precompute maintenance “event” thresholds & types per compressor
    comp_events = {}
    for c, data in compressors.items():
        comp_events[c] = build_event_schedule_for_compressor(
            c, data, total_annual_hours,
            maintenance_types, cumulative_hours_for_maint, costs
        )

    # Binary variables
    y = {}
    for c, events in comp_events.items():
        for i, (thr, mtype) in enumerate(events):
            y[(c, i)] = LpVariable(f"y_{c}_{i}", lowBound=0, upBound=1, cat=LpBinary)

    # Objective
    prob += lpSum(costs[mtype] * y[(c, i)]
                  for c, events in comp_events.items()
                  for i, (thr, mtype) in enumerate(events))

    # Demand constraint
    prob += lpSum(H[c] for c in compressors.keys()) == total_annual_hours

    # Event activation constraints
    BIG_M = total_annual_hours + 3000
    for c, events in comp_events.items():
        for i, (thr, mtype) in enumerate(events):
            prob += H[c] - thr <= BIG_M * y[(c, i)]
            prob += H[c] - thr >= -BIG_M * (1 - y[(c, i)])

    # ✅ Solve
    prob.solve(PULP_CBC_CMD(msg=0))

    # ✅ Debug print (inside function now)
    for c in compressors.keys():
      debug_event_schedule(c, H, y, comp_events[c])


    # ✅ Summarize results
    rows = []
    for c in compressors.keys():
        h = value(H[c])
        evts = comp_events[c]
        maint_counts = {3000: 0, 6000: 0, 21000: 0}
        for i, (thr, mtype) in enumerate(evts):
            if value(y[(c, i)]) >= 0.5:
                maint_counts[mtype] += 1
        total_cost = sum(maint_counts[t] * costs[t] for t in maint_counts)
        
        # Calculate next maintenance dates
        next_maintenances = calculate_next_maintenance_dates(c, compressors[c]['current_hrs'], h)
        next_3k_date = ""
        next_6k_date = ""
        next_21k_date = ""
        
        for maint in next_maintenances:
            if maint['type'] == 3000:
                next_3k_date = maint['date']
            elif maint['type'] == 6000:
                next_6k_date = maint['date']
            elif maint['type'] == 21000:
                next_21k_date = maint['date']
        
        rows.append({
            'Compressor': c,
            'Assigned Hours': h,
            'New Accumulated Hours': compressors[c]['current_hrs'] + h,
            '3K Maint': maint_counts[3000],
            '6K Maint': maint_counts[6000],
            '21K Maint': maint_counts[21000],
            'Next 3K Date': next_3k_date,
            'Next 6K Date': next_6k_date,
            'Next 21K Date': next_21k_date,
            'Exact Cost': total_cost
        })

    df = pd.DataFrame(rows)
    return df


# --- (Optional) Variant with a gentle balancing term ---
def solve_true_min_cost_with_balancing(lambda_balance=0.0001):
    """
    Same exact-cost MIP, plus a tiny penalty on squared deviation from mean hours
    to keep assignments reasonably balanced (convex quadratic approximated via linearization-free trick:
    use sum |H[c]-avg| via aux vars if you prefer a pure LP; here we keep it simple with pairwise spread).
    """
    prob = LpProblem("True_Minimize_Cost_With_Balance", LpMinimize)

    H = {c: LpVariable(f"H_{c}", lowBound=0, upBound=total_annual_hours, cat=LpContinuous)
         for c in compressors.keys()}

    comp_events = {}
    for c, data in compressors.items():
        comp_events[c] = build_event_schedule_for_compressor(
            c, data, total_annual_hours,
            maintenance_types, cumulative_hours_for_maint, costs
        )

    y = {}
    for c, events in comp_events.items():
        for i, (thr, mtype) in enumerate(events):
            y[(c, i)] = LpVariable(f"y_{c}_{i}", lowBound=0, upBound=1, cat=LpBinary)

    # Exact maintenance cost
    exact_cost = lpSum(costs[mtype] * y[(c, i)]
                       for c, events in comp_events.items()
                       for i, (thr, mtype) in enumerate(events))

    # Soft balance: minimize pairwise spread in assigned hours
    keys = list(compressors.keys())
    spread_terms = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            c1, c2 = keys[i], keys[j]
            # introduce aux var for |H[c1]-H[c2]| (linear with two constraints)
            d_ij = LpVariable(f"d_{c1}_{c2}", lowBound=0)
            prob += H[c1] - H[c2] <= d_ij
            prob += H[c2] - H[c1] <= d_ij
            spread_terms.append(d_ij)

    prob += exact_cost + lambda_balance * lpSum(spread_terms)

    prob += lpSum(H[c] for c in compressors.keys()) == total_annual_hours

    BIG_M = total_annual_hours + 3000
    for c, events in comp_events.items():
        for i, (thr, mtype) in enumerate(events):
            prob += H[c] - thr <= BIG_M * y[(c, i)]
            prob += H[c] - thr >= -BIG_M * (1 - y[(c, i)])

    prob.solve(PULP_CBC_CMD(msg=0))

    # Results
    rows = []
    for c in compressors.keys():
        h = value(H[c])
        evts = comp_events[c]
        maint_counts = {3000: 0, 6000: 0, 21000: 0}
        for i, (thr, mtype) in enumerate(evts):
            if value(y[(c, i)]) >= 0.5:
                maint_counts[mtype] += 1
        total_cost = sum(maint_counts[t] * costs[t] for t in maint_counts)
        rows.append({
            'Compressor': c,
            'Assigned Hours': h,
            'New Accumulated Hours': compressors[c]['current_hrs'] + h,
            '3K Maint': maint_counts[3000],
            '6K Maint': maint_counts[6000],
            '21K Maint': maint_counts[21000],
            'Exact Cost': total_cost
        })

    df = pd.DataFrame(rows)
    return df
# --- Precompute cycle state for each compressor ---
for name, data in compressors.items():
    hours_in_cycle = data['current_hrs'] % total_cycle_hours
    sequence_index = 0
    for i, cumulative_hrs in enumerate(cumulative_hours_for_maint):
        if hours_in_cycle < cumulative_hrs:
            sequence_index = i
            break
    else:
        sequence_index = 0  # new cycle

    data['sequence_index'] = sequence_index
    data['hours_in_cycle'] = hours_in_cycle
    next_maint_due_at = cumulative_hours_for_maint[sequence_index]
    data['hrs_until_next_maint'] = next_maint_due_at - hours_in_cycle


def solve_true_min_cost_and_max_gap(lambda_gap=1.0):
    """
    Model 2: Maximize gap between compressor hours while maintaining reasonable costs.
    """
    # Get minimum cost solution as baseline
    min_cost_df = solve_true_min_cost_mip()
    min_cost = min_cost_df['Exact Cost'].sum() if 'Exact Cost' in min_cost_df.columns else 0
    
    if min_cost_df.empty:
        empty_df = pd.DataFrame(columns=[
            'Compressor', 'Assigned Hours', 'New Accumulated Hours',
            '3K Maint', '6K Maint', '21K Maint', 
            'Next 3K Date', 'Next 6K Date', 'Next 21K Date', 'Exact Cost'
        ])
        return empty_df, 0, 0
    
    # Create maximum gap by assigning most hours to one compressor
    compressor_list = list(compressors.keys())
    
    # Find compressor with lowest current hours for maximum gap potential
    min_current_hours = min(compressors[c]['current_hrs'] for c in compressor_list)
    primary_comp = None
    for c in compressor_list:
        if compressors[c]['current_hrs'] == min_current_hours:
            primary_comp = c
            break
    
    # Create assignment that maximizes gap
    assignment = {}
    
    # Give most hours to primary compressor, minimum to others
    primary_hours = total_annual_hours - (len(compressor_list) - 1) * 100  # Leave 100 hours for each other
    assignment[primary_comp] = primary_hours
    
    # Distribute remaining hours equally among other compressors
    remaining_hours = total_annual_hours - primary_hours
    other_comps = [c for c in compressor_list if c != primary_comp]
    hours_per_other = remaining_hours / len(other_comps) if other_comps else 0
    
    for comp in other_comps:
        assignment[comp] = hours_per_other
    
    # Calculate final gap
    accumulated_hours = []
    for c in compressor_list:
        current_hrs = compressors[c]['current_hrs']
        assigned_hrs = assignment[c]
        new_total = current_hrs + assigned_hrs
        accumulated_hours.append(new_total)
    
    final_gap = max(accumulated_hours) - min(accumulated_hours)

    # Build results from assignment
    rows = []
    total_exact_cost = 0
    
    for c in compressors.keys():
        h = assignment[c]
        if h is None:
            h = 0
            
        current_hrs = compressors[c]['current_hrs']
        new_total = current_hrs + h
        
        # Calculate maintenance events triggered by assigned hours
        maint_counts = {3000: 0, 6000: 0, 21000: 0}
        old_cycle_pos = current_hrs % total_cycle_hours
        new_cycle_pos = new_total % total_cycle_hours
        
        # Count maintenance events crossed during assigned hours
        compressor_cost = 0
        for i, maint_threshold in enumerate(cumulative_hours_for_maint):
            if old_cycle_pos < maint_threshold <= new_cycle_pos:
                maint_type = maintenance_types[i]
                maint_counts[maint_type] = 1
                compressor_cost += costs[maint_type]
        
        total_exact_cost += compressor_cost
        
        # Calculate next maintenance dates
        next_maintenances = calculate_next_maintenance_dates(c, current_hrs, h)
        next_3k_date = ""
        next_6k_date = ""
        next_21k_date = ""
        
        for maint in next_maintenances:
            if maint['type'] == 3000:
                next_3k_date = maint['date']
            elif maint['type'] == 6000:
                next_6k_date = maint['date']
            elif maint['type'] == 21000:
                next_21k_date = maint['date']
        
        rows.append({
            'Compressor': c,
            'Assigned Hours': round(h, 1),
            'New Accumulated Hours': round(new_total, 1),
            '3K Maint': maint_counts[3000],
            '6K Maint': maint_counts[6000],
            '21K Maint': maint_counts[21000],
            'Next 3K Date': next_3k_date,
            'Next 6K Date': next_6k_date,
            'Next 21K Date': next_21k_date,
            'Exact Cost': round(compressor_cost, 2)
        })
    
    df = pd.DataFrame(rows)
    
    return df, final_gap, total_exact_cost


def solve_true_min_cost_and_min_gap(lambda_gap=0.1):
    """
    MIP model: minimize exact maintenance cost and minimize the range (gap)
    between accumulated hours across compressors.

    We model the gap as (T_max - T_min) where T_max and T_min bound the new
    accumulated hours of all compressors, and penalize this range in the
    objective.
    """
    prob = LpProblem("True_MinCost_MinGap", LpMinimize)

    # Decision: hours assigned to each compressor
    H = {c: LpVariable(f"H_{c}", lowBound=0, upBound=total_annual_hours, cat=LpContinuous)
         for c in compressors.keys()}

    # Precompute maintenance events
    comp_events = {}
    for c, data in compressors.items():
        comp_events[c] = build_event_schedule_for_compressor(
            c, data, total_annual_hours,
            maintenance_types, cumulative_hours_for_maint, costs
        )

    # Binary event vars
    y = {}
    for c, events in comp_events.items():
        for i, (thr, mtype) in enumerate(events):
            y[(c, i)] = LpVariable(f"y_{c}_{i}", lowBound=0, upBound=1, cat=LpBinary)

    # Range variables
    T_max = LpVariable("T_max", lowBound=0, cat=LpContinuous)
    T_min = LpVariable("T_min", lowBound=0, cat=LpContinuous)
    G = LpVariable("RangeGap", lowBound=0, cat=LpContinuous)

    # Objective: minimize maintenance cost + λ * gap(range)
    exact_cost = lpSum(costs[mtype] * y[(c, i)]
                       for c, events in comp_events.items()
                       for i, (thr, mtype) in enumerate(events))
    prob += exact_cost + lambda_gap * G

    # Demand: total hours = annual requirement
    prob += lpSum(H[c] for c in compressors.keys()) == total_annual_hours

    # Maintenance event activation (big-M)
    BIG_M = total_annual_hours + 3000
    for c, events in comp_events.items():
        for i, (thr, mtype) in enumerate(events):
            prob += H[c] - thr <= BIG_M * y[(c, i)]
            prob += H[c] - thr >= -BIG_M * (1 - y[(c, i)])

    # Range constraints: bound every new total between T_min and T_max
    for c in compressors.keys():
        new_total = compressors[c]['current_hrs'] + H[c]
        prob += new_total <= T_max
        prob += new_total >= T_min

    # Define the gap as the range
    prob += T_max - T_min == G

    # Solve
    prob.solve(PULP_CBC_CMD(msg=0))

    # Collect results
    rows = []
    for c in compressors.keys():
        h = value(H[c])
        evts = comp_events[c]
        maint_counts = {3000: 0, 6000: 0, 21000: 0}
        for i, (thr, mtype) in enumerate(evts):
            if value(y[(c, i)]) >= 0.5:
                maint_counts[mtype] += 1
        total_cost = sum(maint_counts[t] * costs[t] for t in maint_counts)
        
        # Calculate next maintenance dates
        next_maintenances = calculate_next_maintenance_dates(c, compressors[c]['current_hrs'], h)
        next_3k_date = ""
        next_6k_date = ""
        next_21k_date = ""
        
        for maint in next_maintenances:
            if maint['type'] == 3000:
                next_3k_date = maint['date']
            elif maint['type'] == 6000:
                next_6k_date = maint['date']
            elif maint['type'] == 21000:
                next_21k_date = maint['date']
        
        rows.append({
            'Compressor': c,
            'Assigned Hours': h,
            'New Accumulated Hours': compressors[c]['current_hrs'] + h,
            '3K Maint': maint_counts[3000],
            '6K Maint': maint_counts[6000],
            '21K Maint': maint_counts[21000],
            'Next 3K Date': next_3k_date,
            'Next 6K Date': next_6k_date,
            'Next 21K Date': next_21k_date,
            'Exact Cost': total_cost
        })

    df = pd.DataFrame(rows)
    return df, value(G), value(exact_cost)

# --- Example run (replace your main block or add below it) ---
if __name__ == "__main__":
    print("\n--- TRUE MIP: Exact Maintenance Costs ---")
    df_true = solve_true_min_cost_mip()
    print(df_true)
    print(f"\nTotal Assigned Hours: {df_true['Assigned Hours'].sum():.2f}")
    print(f"Total Exact Cost: {df_true['Exact Cost'].sum():.2f}")

    print("\n--- TRUE MIP + Balancing (small lambda) ---")
    df_bal = solve_true_min_cost_with_balancing(lambda_balance=0.0001)
    print(df_bal)
    print(f"\nTotal Assigned Hours: {df_bal['Assigned Hours'].sum():.2f}")
    print(f"Total Exact Cost: {df_bal['Exact Cost'].sum():.2f}")

    print("\n--- TRUE MIP + Max Gap (range) ---")
    df_gap_max, gap_val_max, total_cost_max = solve_true_min_cost_and_max_gap(lambda_gap=0.1)
    print(df_gap_max)
    print(f"\nTotal Assigned Hours: {df_gap_max['Assigned Hours'].sum():.2f}")
    print(f"Total Exact Cost: {total_cost_max:.2f}")
    print(f"Range Gap Achieved (maximized): {gap_val_max:.2f}")

    print("\n--- TRUE MIP + Min Gap (range) ---")
    df_gap_min, gap_val_min, total_cost_min = solve_true_min_cost_and_min_gap(lambda_gap=0.1)
    print(df_gap_min)
    print(f"\nTotal Assigned Hours: {df_gap_min['Assigned Hours'].sum():.2f}")
    print(f"Total Exact Cost: {total_cost_min:.2f}")
    print(f"Range Gap Achieved (minimized): {gap_val_min:.2f}")

