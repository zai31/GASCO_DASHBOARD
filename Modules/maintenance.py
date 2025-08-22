from pulp import *
import pandas as pd

compressors = {
    'A': {'current_hrs': 500},
    'B': {'current_hrs': 79300},
    'C': {'current_hrs': 76900}
}
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


def solve_true_min_cost_and_max_gap(lambda_gap=0.1):
    """
    MIP model: minimize exact maintenance cost and maximize the range (gap)
    between accumulated hours across compressors.

    We model the gap as (T_max - T_min) where T_max and T_min bound the new
    accumulated hours of all compressors.
    """
    prob = LpProblem("True_MinCost_MaxGap", LpMinimize)

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

    # Objective: minimize maintenance cost - λ * gap(range)
    exact_cost = lpSum(costs[mtype] * y[(c, i)]
                       for c, events in comp_events.items()
                       for i, (thr, mtype) in enumerate(events))
    prob += exact_cost - lambda_gap * G

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
    return df, value(G), value(exact_cost)


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

