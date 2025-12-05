"""
Ultra-optimized Flask app that visualizes my_sim.py
"""
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import io
import base64
import numpy as np

# Import my_sim WITHOUT touching it
import my_sim

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global data
counties_gdf = None
is_running = False

# Pre-computed optimization data
geoid_to_geom = {}
geoid_to_idx = {}
geoid_set = set()
border_cache = {}  # (geoid1, geoid2) -> LineString
cmap = None


def load_and_precompute():
    """Load counties and pre-compute all expensive operations."""
    global counties_gdf, geoid_to_geom, geoid_to_idx, geoid_set, border_cache, cmap

    print("Loading counties...")
    counties_gdf = gpd.read_file('data/counties.geojson')
    print(f"Loaded {len(counties_gdf)} counties")

    # Build lookup dicts
    print("Building lookup tables...")
    for idx, row in counties_gdf.iterrows():
        geoid = row['GEOID']
        geoid_to_geom[geoid] = row['geometry']
        geoid_to_idx[geoid] = idx
        geoid_set.add(geoid)

    # Pre-compute ALL county borders
    print("Pre-computing county borders...")
    processed_pairs = set()

    for geoid in my_sim.county_to_neighbors:
        if geoid not in geoid_set:
            continue

        geom1 = geoid_to_geom[geoid]

        for neighbor_geoid in my_sim.county_to_neighbors[geoid]:
            if neighbor_geoid not in geoid_set:
                continue

            # Avoid computing same border twice
            pair = tuple(sorted([geoid, neighbor_geoid]))
            if pair in processed_pairs:
                continue
            processed_pairs.add(pair)

            # Compute shared border once
            geom2 = geoid_to_geom[neighbor_geoid]
            shared = geom1.intersection(geom2)

            if not shared.is_empty and shared.geom_type == 'LineString':
                border_cache[pair] = shared

    print(f"Pre-computed {len(border_cache)} county borders")

    # Create colormap
    cmap = LinearSegmentedColormap.from_list(
        'partisan',
        ['#0015BC', '#6B6BFF', '#FFFFFF', '#FF6B6B', '#BC0000'],
        N=100
    )


def make_map():
    """Generate map using pre-computed data."""
    print(f"[RENDER] Starting render")
    print(f"[RENDER] Border cache size: {len(border_cache)}")

    fig, ax = plt.subplots(figsize=(14, 9), dpi=80)

    # Build color array
    colors = []
    for geoid in counties_gdf['GEOID']:
        if geoid in my_sim.county_to_partisan_lean:
            lean = my_sim.county_to_partisan_lean[geoid]
            normalized = (lean + 20.0) / 40.0
            colors.append(cmap(normalized))
        else:
            colors.append((0.8, 0.8, 0.8, 1.0))

    # Plot counties with THIN borders
    counties_gdf.plot(ax=ax, color=colors, edgecolor='#AAAAAA', linewidth=0.1)

    # Draw state borders THICK and DARK
    state_borders_drawn = 0
    total_borders_checked = 0

    for pair, linestring in border_cache.items():
        geoid1, geoid2 = pair
        state1 = my_sim.county_to_state.get(geoid1)
        state2 = my_sim.county_to_state.get(geoid2)
        total_borders_checked += 1

        if state1 != state2:
            state_borders_drawn += 1
            if state_borders_drawn <= 5:  # Log first 5
                print(f"[RENDER] Drawing state border: {geoid1} ({state1}) <-> {geoid2} ({state2})")
            x, y = linestring.xy
            ax.plot(x, y, color='#FF0000', linewidth=10.0, solid_capstyle='round', zorder=100)

    print(f"[RENDER] Checked {total_borders_checked} borders, drew {state_borders_drawn} state borders")

    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout(pad=0)

    # Faster PNG encoding
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=80, facecolor='white', pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)

    return base64.b64encode(buf.read()).decode('utf-8')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/initial-map')
def initial_map():
    """Get initial map."""
    print(f"[INITIAL] Rendering initial map")
    print(f"[INITIAL] Border cache size: {len(border_cache)}")
    print(f"[INITIAL] my_sim.county_to_state size: {len(my_sim.county_to_state)}")

    # Sample to verify states are assigned
    sample = list(my_sim.county_to_state.items())[:5]
    print(f"[INITIAL] Sample state assignments: {sample}")

    img = make_map()
    return jsonify({'image': img})


@socketio.on('connect')
def on_connect():
    print('Client connected')
    emit('status', {'message': 'Connected'})


@socketio.on('disconnect')
def on_disconnect():
    print('Client disconnected')


@socketio.on('start_algorithm')
def start_algorithm(data):
    """Run simulation."""
    global is_running

    if is_running:
        emit('error', {'message': 'Already running'})
        return

    iterations = data.get('generations', 500)
    print(f"Starting {iterations} iterations")

    def run():
        global is_running
        is_running = True

        # Render every Nth iteration for speed
        render_every = max(1, iterations // 200)  # Cap at ~200 frames max
        print(f"Rendering every {render_every} iterations")

        try:
            for i in range(iterations):
                if not is_running:
                    break

                # ONE county changes per iteration
                my_sim.iteration()

                # Only render every Nth iteration
                if (i + 1) % render_every == 0 or (i + 1) == iterations:
                    img = make_map()

                    socketio.emit('generation_update', {
                        'generation': i + 1,
                        'fitness': 0,
                        'total_generations': iterations,
                        'image': img
                    })

            socketio.emit('algorithm_complete', {
                'final_fitness': 0,
                'generations': iterations
            })

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

    emit('algorithm_started', {'iterations': iterations})


@socketio.on('stop_algorithm')
def stop_algorithm():
    global is_running
    is_running = False
    emit('algorithm_stopped', {'message': 'Stopped'})


if __name__ == '__main__':
    print("="*60)
    print("Initializing...")
    print("="*60)

    # Initialize my_sim
    my_sim.compute_state_to_bordering_counties()
    my_sim.generate_initial_partisan_lean()
    print(f"Initialized: {len(my_sim.state_to_counties)} states, {len(my_sim.county_to_state)} counties")

    # Debug: Check if states are actually assigned
    sample_states = list(my_sim.county_to_state.items())[:10]
    print(f"[DEBUG] Sample county->state mappings: {sample_states}")

    # Load and pre-compute everything
    load_and_precompute()

    print("="*60)
    print("Server starting on http://localhost:5000")
    print("="*60)

    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
