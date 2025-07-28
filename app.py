from flask import Flask, request, jsonify
from flask_cors import CORS
import simpy
from Topology.topology import StarTopology
from Protocols.DPS import node_factory as dps_node_factory, channel_factory as dps_channel_factory, run_dps
from Protocols.COW import node_factory as cow_node_factory, channel_factory as cow_channel_factory, run_cow
from Protocols.BB84 import node_factory as bb84_node_factory, channel_factory as bb84_channel_factory, run_bb84
from Protocols.ProtocolHandler import ProtocolHandler
from Protocols.E91 import node_factory as e91_node_factory, run_e91
import multiprocessing
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# --- Protocol Registry ---
protocols = {
    "DPS": {
        "node_factory": dps_node_factory,
        "channel_factory": dps_channel_factory,
        "run_function": run_dps,
    },
    "COW": {
        "node_factory": cow_node_factory,
        "channel_factory": cow_channel_factory,
        "run_function": run_cow,
    },
    "BB84": {
        "node_factory": bb84_node_factory,
        "channel_factory": bb84_channel_factory,
        "run_function": run_bb84,
    },
    "E91": {
        "node_factory": e91_node_factory,
        "channel_factory": None,      # No physical channel needed, free space
        "run_function": run_e91,
    }
}

#was planning to paralleise running a protocol on each link using python's built in libs
@app.route("/simulate", methods=["POST"])
def simulate():
    data = request.get_json()

    cities = data["cities"]              # List of city/node names
    topology = data["topology"]          # "Star", "Ring", or "Mesh"
    edges = data["edges"]                # List of [cityA, cityB]
    protocols_per_edge = data["protocols"]  # Dict { "cityA-cityB": "DPS" }

    results = []

    for edge in edges:
        node_a, node_b = edge["nodes"]
        distance = edge["distance"]
        protocol_name = protocols_per_edge.get(f"{node_a}-{node_b}") or protocols_per_edge.get(f"{node_b}-{node_a}")
        if protocol_name not in protocols:
            return jsonify({"error": f"Unsupported protocol: {protocol_name}"}), 400

        # Setup handler
        proto = protocols[protocol_name]
        handler = ProtocolHandler(protocol_name, proto["node_factory"], proto["channel_factory"], proto["run_function"])

        # SimPy env and config
        env = simpy.Environment()

        config = {
            "env": env,
            "nodes": {
                node_a: {"role": "Sender", "args": {"num_pulses":  10000}},
                node_b: {"role": "Receiver", "args": {}}
            },
            "channel": {
                "endpoints": (node_a, node_b),
                "args": {"length_meters": 1, "attenuation_db_per_m": 0.0002, "depol_prob": 0.1, "pol_err_std": 1.0}
            },
            "protocol_args": {"num_pulses":  10_00_000}
        }
        if proto.get("channel_factory"):
            config["channel"] = {
                "endpoints": (node_a, node_b),
                "args": {
                    "length_meters": distance,
                    "attenuation_db_per_m": 0.0002,
                    "depol_prob": 0.1,
                    "pol_err_std": 1.0
                }
            }
            hardware_stats = {
            "distance_m": distance,
            "attenuation_db_per_m": config["channel"]["args"]["attenuation_db_per_m"],
            "depol_prob": config["channel"]["args"]["depol_prob"],
            "pol_err_std": config["channel"]["args"]["pol_err_std"],
            "pulse_wavelength_nm": 1550  # example: 1550nm typical telecom wavelength
            }
        else:
            hardware_stats = {
            "distance_m": "Free Space",
            "attenuation_db_per_m": "N/A",
            "depol_prob": "N/A",
            "pol_err_std": "N/A",
            "pulse_wavelength_nm": "N/A"
    }
            
            

        handler.run(config)

        qber = handler.qber
        asym_key_rate=handler.asym_key_rate
        
        result = {
        "protocol": protocol_name,
        "link": f"{node_a} <--> {node_b}",
        "qber": round(qber, 4) if qber is not None else None,
        "key_rate": round(asym_key_rate, 4) if asym_key_rate is not None else 0.0,
        "nodes": {},
        "hardware_stats": hardware_stats
}


        for node_name in [node_a, node_b]:
            node = handler.node_objs.get(node_name)
            if not node:
                continue

            last_sent = node.sent_log[-1][0] if node.sent_log else None
            last_recv = node.recv_log[-1][0] if node.recv_log else None

            result["nodes"][node_name] = {
                "last_sent_time": f"{last_sent:.2e}" if last_sent is not None else None,
                "last_recv_time": f"{last_recv:.2e}" if last_recv is not None else None,
            }

        results.append(result)

    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(port=5000, debug=True)
'''
A couple of points here, so I know where to start next time. 

-Parallelizing the current code via GPU(colab) is not very feasible because:
1. Colab runs  python environements so no .c/.cu. Also, I'd have to re-write this in C.
2. Python GPU parallization is possible via stuff like pytorch- but it is meant to parallelize 
 math and tensor heavy calculation.
3. My intial idea was to run each link+protcol in the topology parallely(which is possible cuz they are independent)
4. But since each protcol has it's own flow+ high level code(not just the calculation), 
 this approach may not work.
5. Possible approaches:
    - use pytorch in the math-y areas: poisson distribution for each pulse, 
     generate pulses ||ly, etc.
    -More viable approach rn: mutli-thread using mutli-cores(for link+protcol)
    using python's built in libs(not GPU though)
    -Re-write in C/C++(but then we'd have to abandon simpy and come up with the event management ourselves)
6. Also about the key rate:
        -The key rate calculation is fine. Basically
        aymptotic key rate= sifted_rate x(1-2H(qber)). this is assumed for an infinite amount of pulses, 
        and highly idealistic scenarios(and post processing).
        The 2 into entropy here denotes the error corection+privacy amplification(neither of which is simulated currently)
         the sifted rate is calculated by taking the final sifted key length and dividing it by thsimulation time.
         The simulation tim is calcuated by dividing the no of pulses by the 
         pulses/ sec(logic)- the pulses per sec are inverse of the frequency which is 1Ghz in our simulation
         So here, unless the sifted key rate is very low, the key rate will be quite high(in the 100s of MBps)
         This is the case with the currently simulated BB84 which has like 500 mbps
         key rate, completely unrealistic. but this happens as the sift rate if 500,000 out of 1,000,000 pulses
         (for some reason pulse loss isn't taking effect- got to look at that)
         But it works quiet well for DPS which has say 12-30 KBps.
        



'''