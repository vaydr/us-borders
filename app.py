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
import colorsys
import io
import base64

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
state_colors = {}  # state_id -> RGBA tuple


def generate_state_colors():
    """Generate visually distinct colors for each state using HSV color space."""
    global state_colors
    states = sorted(my_sim.state_to_counties.keys())
    for i, state in enumerate(states):
        hue = (i * 0.618033988749895) % 1.0
        saturation = 0.55 + (i % 4) * 0.1
        value = 0.80 + (i % 3) * 0.07
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        state_colors[state] = (r, g, b, 1.0)


def load_and_precompute():
    """Load counties and build lookup tables."""
    global counties_gdf, geoid_to_geom, geoid_to_idx, geoid_set

    print("Loading counties...")
    counties_gdf = gpd.read_file('data/counties.geojson')
    print(f"Loaded {len(counties_gdf)} counties")

    print("Building lookup tables...")
    for idx, row in counties_gdf.iterrows():
        geoid = row['GEOID']
        geoid_to_geom[geoid] = row['geometry']
        geoid_to_idx[geoid] = idx
        geoid_set.add(geoid)

    generate_state_colors()
    print(f"Generated colors for {len(state_colors)} states")


def make_map():
    """Generate map using state-based coloring."""
    print(f"[RENDER] Starting render")

    fig, ax = plt.subplots(figsize=(14, 9), dpi=80)

    # Build color array based on state assignment
    colors = []
    for geoid in counties_gdf['GEOID']:
        state = my_sim.county_to_state.get(geoid)
        if state and state in state_colors:
            colors.append(state_colors[state])
        else:
            colors.append((0.8, 0.8, 0.8, 1.0))

    counties_gdf.plot(ax=ax, color=colors, edgecolor='#333333', linewidth=0.15)

    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout(pad=0)

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
    print(f"[INITIAL] State colors: {len(state_colors)}")
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

    iterations = data.get('generations', 25000)
    print(f"Starting {iterations} iterations")

    def run():
        global is_running
        is_running = True

        # Render every Nth iteration for speed
        render_every = 500  # Cap at ~200 frames max
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
