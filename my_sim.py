import numpy as np
import time
import matplotlib.pyplot as plt
county_to_neighbors = {}
county_to_state = {}
state_to_counties = {}
state_to_bordering_counties = {}
county_to_partisan_lean = {}

for line in open('data/county_adjacency.txt'):
    #lines look like: County Name County, AB|69420|Other County, CD|69696|67676
    county_name_state, county_id, adjacent_county_name_state, adjacent_county_id, _ = line.split('|')
    
    state = county_name_state.split(', ')[1]
    if state in ['AK', 'HI']: # skip Alaska and Hawaii as they are not part of the contiguous US
        continue
    adjacent_state = adjacent_county_name_state.split(', ')[1]

    state_to_counties.setdefault(state, set()).add(county_id)
    county_to_neighbors.setdefault(county_id, set()).add(adjacent_county_id)
    county_to_state[county_id] = state


def compute_state_to_bordering_counties():
    global state_to_bordering_counties
    state_to_bordering_counties = {}
    for state, counties in state_to_counties.items():
        for county in counties:
            if county in county_to_neighbors:
                for neighbor in county_to_neighbors[county]:
                    neighbor_state = county_to_state[neighbor]
                    if state != neighbor_state:
                        state_to_bordering_counties.setdefault(state, set()).add(neighbor)

#TODO weighted sampling of states
def sample_state():
    # Compute state ranks based on county count (1 = least counties, 50 = most counties)
    state_county_counts = [(state, len(counties)) for state, counties in state_to_counties.items()]
    state_county_counts.sort(key=lambda x: x[1])  # Sort by county count
    state_ranks = {state: rank + 1 for rank, (state, _) in enumerate(state_county_counts)}

    state_weights = np.exp(np.array([1/(state_ranks[state] ** 2) for state in state_to_counties.keys()]))
    state_weights = state_weights / np.sum(state_weights)

    return np.random.choice(list(state_to_counties.keys()), p=state_weights)

#TODO weighted sampling of adjacent counties
def sample_adjacent_county(state):
    def _number_of_adjacent_states(county):
        return len(set(county_to_state[neighbor] for neighbor in county_to_neighbors[county]))
    county_logits = np.array([1/(_number_of_adjacent_states(county) ** 2) for county in state_to_bordering_counties[state]])
    county_weights = np.exp(county_logits) / np.sum(np.exp(county_logits))
    return np.random.choice(list(state_to_bordering_counties[state]), p=county_weights)
def iteration():
    state_to_grow = sample_state()

    #state eats a random adjacent county
    pivot_county = sample_adjacent_county(state_to_grow)
    state_to_shrink = county_to_state[pivot_county]
    #remove the adjacent county from the old state and add it to the sampled state
    state_to_counties[state_to_grow].add(pivot_county)
    state_to_counties[state_to_shrink].remove(pivot_county)
    county_to_state[pivot_county] = state_to_grow
    #recompute the state to bordering counties
    compute_state_to_bordering_counties()
    if not _is_state_contiguous(state_to_shrink):
        # Reverse the assignments we just made
        state_to_counties[state_to_grow].remove(pivot_county)
        state_to_counties[state_to_shrink].add(pivot_county)
        county_to_state[pivot_county] = state_to_shrink
        # Recompute the state to bordering counties again
        compute_state_to_bordering_counties()
        return
    return

NUM_ITERATIONS = 25000
def generate_initial_partisan_lean():
    #generate a random partisan lean for each county
    global county_to_partisan_lean
    county_to_partisan_lean = {}
    for _, counties in state_to_counties.items():
        state_lean = np.random.uniform(-20, 20)
        for county in counties:
            county_to_partisan_lean[county] = np.random.normal(state_lean, np.abs(state_lean)+1)

def _is_state_contiguous(state):
    counties = state_to_counties[state]
    if not counties:
        return True
    
    # Start BFS from any county in the state
    start_county = next(iter(counties))
    visited = set()
    queue = [start_county]
    visited.add(start_county)
    
    while queue:
        current_county = queue.pop(0)
        if current_county in county_to_neighbors:
            for neighbor in county_to_neighbors[current_county]:
                if neighbor in counties and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
    
    return len(visited) == len(counties)

def main():

    time_start = time.time()
    compute_state_to_bordering_counties()
    print(f"Time taken to compute state to bordering counties: {time.time() - time_start} seconds")
    generate_initial_partisan_lean()
    print(f"Time taken to generate initial partisan lean: {time.time() - time_start} seconds")
    # Track average partisan lean and county count for each state over iterations
    state_names = list(state_to_counties.keys())
    partisan_lean_history = {state: [] for state in state_names}
    county_count_history = {state: [] for state in state_names}
    
    # Record initial values
    for state in state_names:
        counties = state_to_counties[state]
        county_count_history[state].append(len(counties))
        if counties:
            avg_lean = sum(county_to_partisan_lean[county] for county in counties) / len(counties)
        else:
            avg_lean = 0
        partisan_lean_history[state].append(avg_lean)
    
    # Run simulation and record values after each iteration
    for _ in range(NUM_ITERATIONS):
        iteration()
        for state in state_names:
            counties = state_to_counties[state]
            county_count_history[state].append(len(counties))
            if counties:
                avg_lean = sum(county_to_partisan_lean[county] for county in counties) / len(counties)
            else:
                avg_lean = 0
            partisan_lean_history[state].append(avg_lean)
        if _ % 1000 == 0:
            print(f"Iteration {_} completed")
            print(f"Time taken: {time.time() - time_start} seconds")
    
    # Create the plots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12))
    iterations = range(NUM_ITERATIONS + 1)  # +1 to include initial state
    
    # Plot 1: Number of counties per state
    for state in state_names:
        ax1.plot(iterations, county_count_history[state], label=state, alpha=0.7)
    
    ax1.set_xlabel('Iteration')
    ax1.set_ylabel('Number of Counties')
    ax1.set_title('Number of Counties per State Over Iterations')
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Average partisan lean per state
    for state in state_names:
        ax2.plot(iterations, partisan_lean_history[state], label=state, alpha=0.7)
    
    ax2.set_xlabel('Iteration')
    ax2.set_ylabel('Average Partisan Lean')
    ax2.set_title('Average Partisan Lean per State Over Iterations')
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()