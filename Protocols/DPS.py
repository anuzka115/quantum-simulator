import sys
import os
import numpy as np
import simpy
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import key_rate
from Hardware.pulse import Pulse
from Hardware.snspd import SNSPD
from Hardware.node import Node
from Hardware.channel import QuantumChannel
from Hardware.lasers import Laser
from Hardware.sps import SinglePhotonSource
from Hardware.state import QuantumState
from Hardware.MZI import MachZehnderInterferometer


class Alice(Node):
    def __init__(self, node_id, env, num_pulses):
        super().__init__(node_id, env)
        self.num_pulses = num_pulses
        self.sent_phases = []
        self.sent_pulses = []

    def run(self, port_id):
        laser = Laser(wavelength=1550e-9, amplitude=1.0)
        start = time.perf_counter()
        for i in range(self.num_pulses):
            phase = np.random.choice([0, np.pi])
            pulse = laser.emit_pulse(duration=70e-12, phase=phase)
            pulse.mean_photon_number = 0.2
            pulse.pulse_id = i
            self.sent_phases.append(phase)
            self.sent_pulses.append(pulse)
            self.send(port_id, pulse)
            yield self.env.timeout(1e-9)  # 1 ns pulse interval
        end = time.perf_counter()
        print(f"[ALICE] Time to send pulses: {end - start:.2f}s")


class Bob(Node):
    def __init__(self, node_id, env, mzi):
        super().__init__(node_id, env)
        self.mzi = mzi
        self.received_pulses = []
        self.pulse_times = []
        self.bits = []
        self.det_info = []
        
    def receive(self, pulse, receiver_port_id):
        if pulse is None:
            return
        self.received_pulses.append(pulse)
        self.pulse_times.append(self.env.now)
        idx = len(self.received_pulses) - 1
        if idx == 0:
            return
        pulse_prev = self.received_pulses[idx - 1]
        pulse_next = self.received_pulses[idx]
        t = self.pulse_times[idx]
        bit, info = self.mzi.measure(pulse_prev, pulse_next, current_time=t)
        if bit is not None:
         
            pulse_prev_id = pulse_prev.pulse_id
            pulse_next_id = pulse_next.pulse_id
            self.bits.append((pulse_prev_id, pulse_next_id, bit))
            self.det_info.append(info)


def run_dps(alice: Alice, bob: Bob, channel:QuantumChannel, env, num_pulses=10_00_000, **kwargs):
    

    alice.assign_port("qport", "quantum_out")
    bob.assign_port("qport", "quantum_in")
    alice.connect_nodes("qport", "qport", bob, channel)

    # --- Run Simulation ---
    env.process(alice.run("qport"))
    sim_time = (num_pulses + 10) * 1e-6
    env.run(until=sim_time)

   


    bob_ids, bob_next_ids, bob_bits = zip(*bob.bits) if bob.bits else ([], [], [])

    
    alice_bits_for_bob = []
    for prev_id, next_id in zip(bob_ids, bob_next_ids):
        if prev_id is None or next_id is None:
            alice_bits_for_bob.append(None)
            continue
        # Only compare if indices are adjacent (should be for proper DPS key)
        if next_id - prev_id == 1:
            phase_diff = (alice.sent_phases[next_id] - alice.sent_phases[prev_id]) % (2 * np.pi)
            bit = 0 if abs(phase_diff) < 1e-6 or abs(phase_diff - 2 * np.pi) < 1e-6 else 1
            alice_bits_for_bob.append(bit)
        else:
            alice_bits_for_bob.append(None)  # Or skip
    # Filter out any Nones
    final_alice_bits = [a for a in alice_bits_for_bob if a is not None]
    final_bob_bits   = [b for a, b in zip(alice_bits_for_bob, bob_bits) if a is not None]

    L = len(final_bob_bits)
    errors = sum(a != b for a, b in zip(final_alice_bits, final_bob_bits))
    qber = errors / L if L else 0
    sim_time = (num_pulses + 10) * 1e-9
    sifted_key_rate = L / sim_time
    print("Sifted key rate", sifted_key_rate)
    asym_key_rate=key_rate.compute_key_rate(qber, sifted_key_rate)
    print("QBER", qber)
    print( asym_key_rate)
    return qber, asym_key_rate
    

def node_factory(name, role, env, num_pulses=10_00_000):
    if role == "Sender":
        return Alice(name, env, num_pulses=num_pulses)
    elif role == "Receiver":
        snspd0 = SNSPD(efficiency=0.9, dark_count_rate=10, dead_time=30e-9, timing_jitter=30e-12)
        snspd1 = SNSPD(efficiency=0.9, dark_count_rate=10, dead_time=30e-9, timing_jitter=30e-12)
        mzi = MachZehnderInterferometer(snspd0=snspd0, snspd1=snspd1, visibility=0.98, phase_noise_std=0.2)
        return Bob(name, env, mzi)
    else:
        return Node(name, env)


def channel_factory (a, b, length_meters, attenuation_db_per_m, depol_prob, pol_err_std=None):
    return QuantumChannel(
        name=f"{a}_{b}",
        length_meters=length_meters,
        attenuation_db_per_m= attenuation_db_per_m,
        depol_prob=depol_prob,
        pol_err_std=pol_err_std
    )
#'''
env=simpy.Environment()
alice=Alice("al", env, 10_00_000)
snspd0 = SNSPD(efficiency=0.9, dark_count_rate=10, dead_time=30e-9, timing_jitter=30e-12)
snspd1 = SNSPD(efficiency=0.9, dark_count_rate=10, dead_time=30e-9, timing_jitter=30e-12)
mzi = MachZehnderInterferometer(snspd0=snspd0, snspd1=snspd1, visibility=0.98, phase_noise_std=0.2)
bob=Bob("bob", env, mzi)
channel=QuantumChannel(
        name="q_chan",
        length_meters=90_000,
        attenuation_db_per_m= 0.0002,
        depol_prob=0.1,
        pol_err_std=1
    )
run_dps(alice, bob, channel, env, num_pulses=10_00_000)
    
#'''
