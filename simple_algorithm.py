"""
Simple iterative border redistricting algorithm.
Much simpler than genetic algorithm - just randomly consume neighboring counties.
"""

import numpy as np
import random
from collections import defaultdict


class SimpleRedistrictingAlgorithm:
    """
    Simple algorithm: repeatedly pick a state and consume a neighboring county.
    Uses heuristics to balance state sizes and political homogeneity.
    """

    def __init__(self, counties_data, neighbors, num_states=50):
        self.counties = counties_data
        self.neighbors = neighbors
        self.num_states = num_states

        # Create mapping
        self.fips_list = self.counties['FIPS'].tolist()
        self.fips_to_idx = {fips: idx for idx, fips in enumerate(self.fips_list)}
        self.num_counties = len(self.fips_list)

        # Precompute data
        self.political_leans = self.counties['political_lean'].fillna(0).values
        self.populations = self.counties['POP'].fillna(100000).values

        # Convert neighbor dict to indices
        self.neighbor_indices = {}
        for fips, neighbor_fips in neighbors.items():
            if fips in self.fips_to_idx:
                idx = self.fips_to_idx[fips]
                self.neighbor_indices[idx] = [
                    self.fips_to_idx[n] for n in neighbor_fips if n in self.fips_to_idx
                ]

        # Initialize with current state assignments
        self.solution = self._initialize_solution()

    def _initialize_solution(self):
        """Start with actual US state borders."""
        if 'STATEFP' in self.counties.columns:
            original_states = self.counties['STATEFP'].values
            unique_states = sorted(set(original_states))

            print(f"\n=== INITIALIZATION DEBUG ===")
            print(f"Found {len(unique_states)} unique state FIPS codes: {unique_states}")
            print(f"Need exactly {self.num_states} states")

            if len(unique_states) > self.num_states:
                print(f"WARNING: More than {self.num_states} states found! Taking first {self.num_states}")
                unique_states = unique_states[:self.num_states]

            state_mapping = {old: new for new, old in enumerate(unique_states)}
            solution = np.array([state_mapping.get(s, 0) for s in original_states])

            # Verify no states got mapped to 0 incorrectly
            unmapped = set(original_states) - set(unique_states)
            if unmapped:
                print(f"ERROR: These state codes were NOT mapped and defaulted to state 0: {unmapped}")
                for state_code in unmapped:
                    num_counties = np.sum(original_states == state_code)
                    print(f"  State {state_code}: {num_counties} counties assigned to state 0!")

            print(f"Initial solution has {len(np.unique(solution))} unique states")
            print(f"=== END DEBUG ===\n")

            # Ensure exactly 50 states
            while len(np.unique(solution)) < self.num_states:
                # Split largest state
                state_sizes = [(s, np.sum(solution == s)) for s in np.unique(solution)]
                largest = max(state_sizes, key=lambda x: x[1])[0]
                counties_in_largest = np.where(solution == largest)[0]
                split_point = len(counties_in_largest) // 2
                new_state_id = np.max(solution) + 1
                solution[counties_in_largest[split_point:]] = new_state_id

            # Remap to 0-49
            unique = np.unique(solution)
            mapping = {old: new for new, old in enumerate(unique)}
            solution = np.array([mapping[s] for s in solution])

            return solution
        else:
            # Create random valid solution
            return self._create_random_solution()

    def _create_random_solution(self):
        """Create random solution with exactly num_states."""
        solution = np.zeros(self.num_counties, dtype=int)
        seed_counties = np.random.choice(self.num_counties, self.num_states, replace=False)
        for state_id, county_idx in enumerate(seed_counties):
            solution[county_idx] = state_id
        unassigned = [i for i in range(self.num_counties) if i not in seed_counties]
        for county_idx in unassigned:
            solution[county_idx] = np.random.randint(0, self.num_states)
        return solution

    def get_state_stats(self):
        """Get current statistics about states."""
        state_pops = np.array([np.sum(self.populations[self.solution == s])
                               for s in range(self.num_states)])
        state_leans = np.array([np.mean(self.political_leans[self.solution == s])
                                for s in range(self.num_states)])
        return state_pops, state_leans

    def find_annexable_counties(self, state_id):
        """
        Find all border counties from neighboring states that this state could annex.
        Returns list of (county_idx, neighbor_state_id) tuples.
        """
        annexable = []

        # Find all counties in this state
        state_counties = np.where(self.solution == state_id)[0]

        # Find their neighbors in OTHER states
        for county_idx in state_counties:
            for neighbor_idx in self.neighbor_indices.get(county_idx, []):
                neighbor_state = self.solution[neighbor_idx]

                if neighbor_state != state_id:
                    # This neighbor is in a different state
                    # Check if we can take it without making that state empty
                    state_size = np.sum(self.solution == neighbor_state)

                    if state_size > 1:  # Can't take if it would empty the state
                        annexable.append((neighbor_idx, neighbor_state))

        return annexable

    def select_county_to_annex(self, state_id, annexable_counties):
        """
        Select which county to annex using heuristics.
        Prioritizes:
        1. Making state sizes more equal
        2. Increasing political homogeneity
        """
        if not annexable_counties:
            return None

        state_pops, state_leans = self.get_state_stats()
        target_pop = np.sum(self.populations) / self.num_states
        current_state_pop = state_pops[state_id]
        current_state_lean = state_leans[state_id]

        scores = []
        for county_idx, _ in annexable_counties:
            county_pop = self.populations[county_idx]
            county_lean = self.political_leans[county_idx]

            # Score based on:
            # 1. Would this move us closer to target population?
            new_pop = current_state_pop + county_pop
            pop_score = -abs(new_pop - target_pop)  # Closer to target is better

            # 2. Is this county politically similar to our state?
            homogeneity_score = -abs(county_lean - current_state_lean)

            # Combined score (weight population balance more)
            total_score = 5.0 * pop_score + 1.0 * homogeneity_score
            scores.append(total_score)

        # Pick best scoring county
        best_idx = np.argmax(scores)
        return annexable_counties[best_idx][0]

    def run_iteration(self):
        """
        Run one iteration: pick a state (weighted by partisan lean) and try to annex a county.
        Returns True if successful, False if no moves possible.
        """
        # Calculate state leans for weighting
        state_pops, state_leans = self.get_state_stats()

        # Weight by TWO factors:
        # 1. Absolute partisan lean (more partisan = selected more)
        abs_leans = np.abs(state_leans)
        lean_weights = abs_leans + 0.1  # Add small constant to avoid zero weights

        # 2. Inverse size (fewer counties = selected more)
        state_sizes = np.array([np.sum(self.solution == s) for s in range(self.num_states)])
        size_weights = 1.0 / (state_sizes + 1.0)  # +1 to avoid division by zero

        # Combine both factors multiplicatively
        weights = lean_weights * size_weights
        weights = weights / np.sum(weights)  # Normalize

        # Pick a state with probability proportional to both lean and inverse size
        state_id = np.random.choice(self.num_states, p=weights)

        # Find counties we could annex
        annexable = self.find_annexable_counties(state_id)

        if not annexable:
            return False

        # Select which county to annex
        county_to_annex = self.select_county_to_annex(state_id, annexable)

        if county_to_annex is not None:
            # Annex it!
            self.solution[county_to_annex] = state_id
            return True

        return False

    def run(self, num_iterations, callback=None):
        """
        Run the algorithm for a specified number of iterations.

        Args:
            num_iterations: Number of iterations to run
            callback: Function called with (iteration, solution) after each iteration
                     Callback can return False to stop the algorithm early
        """
        print(f"Running simple iterative algorithm for {num_iterations} iterations...")

        successful_moves = 0

        for iteration in range(num_iterations):
            success = self.run_iteration()

            if success:
                successful_moves += 1

            # Call callback for visualization
            if callback:
                should_continue = callback(iteration + 1, self.solution.copy())
                if should_continue is False:
                    print(f"\nStopped early at iteration {iteration + 1}")
                    break

        print(f"\nCompleted {iteration + 1} iterations")
        print(f"Successful moves: {successful_moves}")

        return self.solution
