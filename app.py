"""
Ultra-optimized Flask app that visualizes my_sim.py
Client-side rendering - server only sends color mappings
"""
from flask import Flask, render_template, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import time
import json

# Import my_sim WITHOUT touching it
import my_sim

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global data
is_running = False

# Saved initial state for reset
initial_county_to_state = {}
initial_state_to_counties = {}

# 49 maximally distinguishable colors
PALETTE = [
    "#c5003a", "#01d97a", "#c00a9d", "#66d248", "#7d4fd6",
    "#b1e03b", "#2c50d5", "#b1c300", "#a936bc", "#ccff6c",
    "#d979ff", "#f5ca1e", "#0054c4", "#ffdd59", "#418cff",
    "#fffb81", "#7638a4", "#86ffa8", "#ff2f90", "#1d7200",
    "#f78dff", "#587a00", "#b990ff", "#ad8500", "#007dda",
    "#ff9e35", "#69509a", "#b1ffb4", "#bd0067", "#00eedd",
    "#f72a58", "#01b887", "#ff7bcb", "#417833", "#e29eff",
    "#cd8100", "#816fbd", "#f76926", "#a390e1", "#9e4900",
    "#922c7d", "#7a9746", "#ac1621", "#e1c571", "#9c2c4a",
    "#ff9f63", "#e47799", "#b17d3a", "#973725",
]

# state_id -> palette index (fixed at startup)
state_color_idx = {}


def generate_state_colors():
    """Assign each state a unique color index."""
    global state_color_idx
    state_color_idx = {}

    states = sorted([str(s) for s in my_sim.state_to_counties.keys()])
    for i, state in enumerate(states):
        state_color_idx[state] = i % len(PALETTE)


def get_county_colors():
    """Get county_id -> color_index mapping."""
    return {str(geoid): state_color_idx.get(str(state), 0)
            for geoid, state in my_sim.county_to_state.items()}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/geojson')
def get_geojson():
    """Serve the counties GeoJSON file."""
    return send_file('data/counties.geojson', mimetype='application/json')


def get_state_partisan_leans():
    """Calculate population-weighted average partisan lean for each state."""
    state_leans = {}
    for state, counties in my_sim.state_to_counties.items():
        if counties:
            total_pop = sum(my_sim.county_to_population.get(c, 0) for c in counties)
            if total_pop > 0:
                avg_lean = sum(
                    my_sim.county_to_partisan_lean.get(c, 0) * my_sim.county_to_population.get(c, 0)
                    for c in counties
                ) / total_pop
                state_leans[str(state)] = avg_lean
            else:
                state_leans[str(state)] = 0
        else:
            state_leans[str(state)] = 0
    return state_leans


def get_election_results():
    """Compute election winner using my_sim's logic."""
    my_sim.compute_state_to_partisan_lean()
    winner, winner_ev, loser_ev = my_sim.compute_election_winner()

    # Determine R and D EVs
    if winner == 'Republican':
        r_ev, d_ev = winner_ev, loser_ev
    elif winner == 'Democratic':
        r_ev, d_ev = loser_ev, winner_ev
    else:  # Tie
        r_ev, d_ev = winner_ev, loser_ev

    return {
        'winner': winner,
        'r_ev': r_ev,
        'd_ev': d_ev
    }


@app.route('/api/init')
def init_data():
    """Get initial state: palette, county colors, neighbor data, and partisan lean."""
    # Build neighbors dict with string keys
    neighbors = {}
    for geoid, neighbor_list in my_sim.county_to_neighbors.items():
        neighbors[str(geoid)] = [str(n) for n in neighbor_list]

    # Build partisan lean dict with string keys
    partisan_lean = {str(geoid): lean for geoid, lean in my_sim.county_to_partisan_lean.items()}

    # Build population dict with string keys
    population = {str(geoid): pop for geoid, pop in my_sim.county_to_population.items()}

    # Build county to state mapping
    county_to_state_map = {str(geoid): str(state) for geoid, state in my_sim.county_to_state.items()}

    # Build state EVs and populations
    state_evs = dict(my_sim.state_to_ev)
    state_populations = {}
    for state, counties in my_sim.state_to_counties.items():
        state_populations[state] = sum(my_sim.county_to_population.get(c, 0) for c in counties)

    return jsonify({
        'palette': PALETTE,
        'colors': get_county_colors(),
        'neighbors': neighbors,
        'partisanLean': partisan_lean,
        'population': population,
        'stateLeans': get_state_partisan_leans(),
        'countyToState': county_to_state_map,
        'stateEVs': state_evs,
        'statePopulations': state_populations,
        'election': get_election_results()
    })


@socketio.on('connect')
def on_connect():
    print('Client connected')
    emit('status', {'message': 'Connected'})


@socketio.on('disconnect')
def on_disconnect():
    print('Client disconnected')


def get_current_score(target):
    """Get current configuration score for the given target."""
    my_sim.compute_state_to_partisan_lean()
    return my_sim.get_configuration_score(target)


@socketio.on('start_algorithm')
def start_algorithm(data):
    """Run simulation - sends only color updates, not images."""
    global is_running

    if is_running:
        emit('error', {'message': 'Already running'})
        return

    iterations = data.get('generations', 25000)
    render_every = data.get('render_every', 50)
    target = data.get('target', 'Republican')  # 'Republican', 'Democratic', or 'Tie'
    mode = data.get('mode', 'standard')  # 'standard' or 'follow_the_leader'
    print(f"Starting {iterations} iterations, updating every {render_every}, target: {target}, mode: {mode}")

    # Reset follow-the-leader state at start
    my_sim.reset_follow_the_leader()

    def run():
        global is_running
        is_running = True

        try:
            for i in range(iterations):
                if not is_running:
                    break

                my_sim.iteration_greedy(target, mode)

                # Send color update every N iterations
                if (i + 1) % render_every == 0 or (i + 1) == iterations:
                    # Don't regenerate colors - state colors are fixed at startup
                    socketio.emit('color_update', {
                        'generation': i + 1,
                        'total': iterations,
                        'colors': get_county_colors(),
                        'stateLeans': get_state_partisan_leans(),
                        'countyToState': {str(geoid): str(state) for geoid, state in my_sim.county_to_state.items()},
                        'election': get_election_results(),
                        'score': get_current_score(target)
                    })

            socketio.emit('algorithm_complete', {'generations': iterations})

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            socketio.emit('error', {'message': str(e)})

        finally:
            is_running = False

    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()

    emit('algorithm_started', {'iterations': iterations, 'target': target})


@socketio.on('stop_algorithm')
def stop_algorithm():
    global is_running
    is_running = False
    emit('algorithm_stopped', {'message': 'Stopped'})


@socketio.on('reset_algorithm')
def reset_algorithm():
    global is_running
    is_running = False

    # Restore initial state from saved copies
    my_sim.county_to_state.clear()
    my_sim.county_to_state.update(initial_county_to_state)

    my_sim.state_to_counties.clear()
    for state, counties in initial_state_to_counties.items():
        my_sim.state_to_counties[state] = set(counties)

    my_sim.compute_state_to_bordering_counties()
    my_sim.reset_follow_the_leader()

    print("Algorithm reset to initial state")
    emit('reset_complete', {
        'colors': get_county_colors(),
        'stateLeans': get_state_partisan_leans(),
        'countyToState': {str(geoid): str(state) for geoid, state in my_sim.county_to_state.items()},
        'election': get_election_results()
    })


if __name__ == '__main__':
    print("="*60)
    print("Initializing...")
    print("="*60)

    # Initialize my_sim
    my_sim.compute_state_to_bordering_counties()
    my_sim.generate_initial_partisan_lean(2020)
    print(f"Initialized: {len(my_sim.state_to_counties)} states, {len(my_sim.county_to_state)} counties")

    # Save initial state for reset functionality
    initial_county_to_state.update(my_sim.county_to_state)
    for state, counties in my_sim.state_to_counties.items():
        initial_state_to_counties[state] = set(counties)
    print("Saved initial state for reset")

    # Generate initial state colors
    generate_state_colors()
    print(f"Generated colors for {len(state_color_idx)} states")

    print("="*60)
    print("Server starting on http://localhost:5000")
    print("="*60)

    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
