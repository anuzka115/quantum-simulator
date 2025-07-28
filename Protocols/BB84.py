import sys
import os
import simpy
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Hardware.node import Node
from Hardware.channel import QuantumChannel
from Hardware.pulse import Pulse
from Hardware.snspd import SNSPD
from Hardware.PBS import PolarizingBeamSplitter
from Hardware.HWP import HalfWavePlate
from utils import key_rate

# Error parameters (tune as needed)
POL_ERR_STD = 1.0            # degrees → perfect polarization preservation
BOB_HWP_ERR_STD = 0.0        # degrees → Bob's HWP set exactly
PBS_ANGLE_JITTER_STD = 0.0   # degrees → no misalignment in PBS
PBS_EXTINCTION_DB = 60.0     # dB → nearly perfect PBS (realistic ideal)
DARK_COUNT_RATE = 10          # Hz → no dark counts at SNSPD
SNSPD_EFFICIENCY = 0.9       # perfect detection efficiency (100%)
SNSPD_JITTER = 40e-12          # seconds → perfect timing resolution

# Basis and bit mapping for Alice
alice_hwp_basis_map = {0: 'plus', 45: 'plus', -22.5: 'cross', 22.5: 'cross'}
alice_hwp_bit_map = {0: 0, 45: 1, -22.5: 0, 22.5: 1}

# Basis and bit mapping for Bob
bob_hwp_basis_map = {0: 'plus', 22.5: 'cross'}
bob_hwp_bit_map = {0: 0, 22.5: 1}

class Alice(Node):
    def __init__(self, node_id, env, num_pulses):
        super().__init__(node_id, env)
        self.assign_port('q', 'quantum')
        self.num_pulses = num_pulses
        self.pulses = []
        self.hwp_angles = []
        self.bases = []
        self.bits = []
        self.after_hwp_pols = []

    def run(self, port_id):
        self.sent_bits = {}    # pulse_id: bit
        self.sent_bases = {}   # pulse_id: basis
        self.sent_pulses = []  # optional: store pulses
        for i in range(self.num_pulses):
            hwp_angle = np.random.choice([0, 45, -22.5, 22.5])
            basis = alice_hwp_basis_map[hwp_angle]
            bit = alice_hwp_bit_map[hwp_angle]

            self.hwp_angles.append(hwp_angle)
            self.bases.append(basis)
            self.bits.append(bit)

            pulse = Pulse(wavelength=1550e-9, duration=70e-12, amplitude=1.0, polarization=0.0)
            pulse.mean_photon_number = 10
            pulse.pulse_id = i  # easier to use for qber calculation
            hwp = HalfWavePlate(theta_deg=hwp_angle)
            pulse = hwp.apply(pulse)

            self.after_hwp_pols.append(pulse.polarization)
            self.pulses.append(pulse)

            
            self.sent_bits[i] = bit
            self.sent_bases[i] = basis
            self.sent_pulses.append(pulse)

            self.send(port_id, pulse)
            yield self.env.timeout(1e-9) #frequency of pulse= 1/1ns = 10^9 Hz / 1GHz



class Bob(Node):
    def __init__(self, node_id, env):
        super().__init__(node_id, env)
        self.assign_port('q', 'quantum')
        self.snspd_H = SNSPD(
            efficiency=SNSPD_EFFICIENCY,
            dark_count_rate=DARK_COUNT_RATE,
            dead_time=30e-9,
            timing_jitter=SNSPD_JITTER
        )
        self.snspd_V = SNSPD(
            efficiency=SNSPD_EFFICIENCY,
            dark_count_rate=DARK_COUNT_RATE,
            dead_time=30e-9,
            timing_jitter=SNSPD_JITTER
        )
        self.pbs = PolarizingBeamSplitter(
            extinction_ratio_db=PBS_EXTINCTION_DB,
            angle_jitter_std=PBS_ANGLE_JITTER_STD
        )
        self.basis_angles = []
        self.bases = []
        self.bits = []
        self.clicks = []
        self.det_pols = []
        self.recv_log = []  # List of tuples: (recv_time, basis, detected_bit, click_status)
        self.received_ids = []
        self.received_bits = {}
        self.received_bases = {}

    def receive(self, data, receiver_port_id):
        if receiver_port_id != 'q' or data is None:
            return

        # --- Channel polarization noise ---
        data.polarization = (data.polarization + np.random.normal(0, POL_ERR_STD)) % 180

        # --- Bob's HWP setting with error ---
        hwp_angle_nom = np.random.choice([0, 22.5])
        hwp_angle = hwp_angle_nom + np.random.normal(0, BOB_HWP_ERR_STD)
        basis = bob_hwp_basis_map[hwp_angle_nom]
        bit = bob_hwp_bit_map[hwp_angle_nom]
        self.basis_angles.append(hwp_angle_nom)
        self.bases.append(basis)
        self.bits.append(bit)
        hwp = HalfWavePlate(theta_deg=hwp_angle)
        data = hwp.apply(data)
        self.det_pols.append(data.polarization)
        port = self.pbs.split(data)
        if port == 'H':
            click, _ = self.snspd_H.detect(data, self.env.now)
            if click:
                pulse_id = data.pulse_id
                self.received_ids.append(pulse_id)
                self.received_bases[pulse_id] = basis
                self.received_bits[pulse_id] = 0
                self.clicks.append('H')
            else:
                self.clicks.append('None')
        elif port == 'V':
            click, _ = self.snspd_V.detect(data, self.env.now)
            if click:
                pulse_id = data.pulse_id
                self.received_ids.append(pulse_id)
                self.received_bases[pulse_id] = basis
                self.received_bits[pulse_id] = 1
                self.clicks.append('V')
            else:
                self.clicks.append('None')
        else:
            self.clicks.append('None')



def run_bb84(alice: Alice, bob: Bob, channel:QuantumChannel, env, num_pulses=1000000, **kwargs):
    
    
    print(f"[run_bb84] alice: {type(alice)}, bob: {type(bob)}")

    alice.connect_nodes('q', 'q', bob, channel)
    env.process(alice.run('q'))

    # run long enough for all pulses
    total_time = num_pulses * 1e-9 + 5e-9
    env.run(until=total_time)

    # only loop over pulses that both parties actually processed
    n = min(len(alice.bits), len(bob.bits), len(bob.clicks))
    sifted_alice = []
    sifted_bob   = []

    for i in range(n):
        # basis‐match check
        if alice.bases[i] != bob.bases[i]:
            continue
        common_ids = set(bob.received_ids) & set(alice.sent_bits.keys())
        # derive Bob's bit
        for pid in common_ids:
            if alice.sent_bases[pid] == bob.received_bases[pid]:
                sifted_alice.append(alice.sent_bits[pid])
                sifted_bob.append(bob.received_bits[pid])

    sim_time = (num_pulses) * 1e-9
    sifted_key_rate = len(sifted_alice) / sim_time

    if sifted_alice:
        errors = sum(a != b for a, b in zip(sifted_alice, sifted_bob))
        qber   = errors / len(sifted_alice)
        
        asym_key_rate=key_rate.compute_key_rate(qber, sifted_key_rate)
        print(qber, sifted_key_rate, asym_key_rate, len(sifted_alice))
        return qber, asym_key_rate

    else:
        return None, None
        print("No sifted bits to compute QBER.")
   

def node_factory(name, role, env, num_pulses=10000):
    if role == "Sender":
        return Alice(name, env, num_pulses=num_pulses)
    elif role == "Receiver":
        
         return Bob(name, env) #here name=node_id
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

