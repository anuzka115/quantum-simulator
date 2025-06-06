from flask import Flask, request, jsonify
from flask_cors import CORS
from COW_netsquid import run_cow_protocol
from dps_final_1 import run_dps_protocol
app = Flask(__name__)
CORS(app)  



@app.route('/simulate', methods=['POST'])
def simulate():
    data = request.get_json()

    num_pulses = int(data.get('num_pulses', 10))
    delay = float(data.get('delay', 1))
    channel_length = float(data.get('channel_length', 1))
    protocol = data.get('protocol', 'COW')  # Default to COW if not specified

    
    depolar_rate = 0.01
    noise_model = "DepolarNoiseModel"

    if protocol == 'DPS':
        qber, alice_key, bob_key = run_dps_protocol(
            #num_pulses=num_pulses,
            #delay=delay,
            length=channel_length,
            #noise_model=noise_model
        )
    elif protocol == 'COW':
        qber, alice_key, bob_key = run_cow_protocol(
            num_pulses=num_pulses,
            delay=delay,
            depolar_rate=depolar_rate,
            length=channel_length,
            noise_model=noise_model
        )
    else:
        return jsonify({"error": "Unsupported protocol"}), 400

    return jsonify({
        "qber": qber,
        "alice_key": list(alice_key),
        "bob_key": list(bob_key)
    })


if __name__ == '__main__':
    app.run(debug=True)
