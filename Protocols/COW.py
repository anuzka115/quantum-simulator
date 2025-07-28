import sys
import os
import simpy
import numpy as np

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import key_rate
from Hardware.node import Node
from Hardware.lasers import Laser
from Hardware.channel import QuantumChannel
from Hardware.snspd import SNSPD
from Hardware.MZI import MachZehnderInterferometer  
def quantize_time(t, bin_width=1e-9): #basically returns x ns as x
    return round(t / bin_width)

class Alice(Node):
    def __init__(self, node_id, env, num_pulses, decoy_prob):
        super().__init__(node_id, env)
        self.env = env
        self.num_pulses = num_pulses
        self.decoy_prob = decoy_prob
        self.bit_log = [] # bit, is_decoy
        #self.actual_key = []

    def run(self, port_id):
        laser = Laser(wavelength=1550e-9, amplitude=1.0)
        self.add_component("laser", laser)

        for _ in range(self.num_pulses):
            is_decoy = np.random.rand() < self.decoy_prob
            bit = None
            indices = [0, 1] if is_decoy else [np.random.choice([0, 1])]
            self.bit_log.append((indices[0] if not is_decoy else None, is_decoy))

            for i in range(2):
                if i in indices:
                    pulse = laser.emit_pulse(duration=70e-12)
                    pulse.mean_photon_number = 0.5
                    if pulse.sample_photon_arrivals(): #poisson sampling, about 9% of the time gives 1.
                        self.send(port_id, pulse)
                yield self.env.timeout(2e-9)

class Bob(Node):
    def __init__(self, node_id, env, snspd:SNSPD,  monitor_ratio=0.0, threshold=5):
        super().__init__(node_id, env)
        self.monitor_ratio = monitor_ratio
        self.threshold = threshold
        self.sifted_key = []
        self.monitor_results = []
        self.time_bin_map = {}
        self.last_processed_bin = None
        self.dm2_count = 0
        self.last_monitor_pulse = None
        self.sns_detector = snspd
        self.mzi = MachZehnderInterferometer(
        visibility=0.98,
        phase_noise_std=0.02,
    )

    def receive(self, pulse, receiver_port_id):
        super().receive(pulse, receiver_port_id)
        if pulse is None:
            return
        if np.random.rand() < self.monitor_ratio: #10 percent of the time goes to monitor line
            self._monitor_line(pulse)
        else:
            self._data_line(pulse) #90 perccent does to data line
#this entire part should be replaced with detector logic, realisticlally, speaking
    def _data_line(self, pulse):
        #bin_time = quantize_time(self.env.now)
        
        click, detection_info = self.sns_detector.detect(pulse, self.env.now)
        if not click:
            return
        bin_time = quantize_time(detection_info["detection_time"])
        

        self.time_bin_map[bin_time] = True
        if self.last_processed_bin is not None:
            for t in range(self.last_processed_bin + 1, bin_time):
                self.time_bin_map[t] = False
        self.last_processed_bin = bin_time
       


    def _process_bin_pairs(self):
        sorted_bins = sorted(self.time_bin_map.keys())
        i = 0
        while i < len(sorted_bins) - 1:
            t1 = sorted_bins[i]
            if t1 % 2 == 1: #odd bins
                i += 1
                continue
            t2 = sorted_bins[i + 1]
            if t2 != t1 + 1:  #non-consecutive
                i += 1
                continue
            p1 = self.time_bin_map[t1] #gives true/false, depending on whether a pulse was observed
            p2 = self.time_bin_map[t2]
            if p1 and not p2:
                self.sifted_key.append((t1, 0))
            elif not p1 and p2:
                self.sifted_key.append((t2, 1))
            sorted_bins = sorted_bins[i+2:]  # Remove processed bins
            i = 0

    def _monitor_line(self, pulse):
        if self.last_monitor_pulse is None:
            self.last_monitor_pulse = pulse
            return

        bit, detection_info = self.mzi.measure(self.last_monitor_pulse, pulse, current_time=self.env.now)
        if bit == 0:
            self.monitor_results.append(('DM1', self.env.now))
        elif bit == 1:
            self.monitor_results.append(('DM2', self.env.now))
            self.dm2_count += 1

        self.last_monitor_pulse = None

    def check_security(self):
        return self.dm2_count <= self.threshold

def run_cow(alice, bob, channel, env, num_pulses=1000):
    #env = simpy.Environment()
    #num_pulses = 10000
    decoy_prob = 0.1

    

    alice.assign_port("qport", "quantum_out")
    bob.assign_port("qport", "quantum_in")

    channel = QuantumChannel("Alice_Bob_Channel", length_meters=10, attenuation_db_per_m=0.0003, depol_prob=0.0)
    alice.connect_nodes("qport", "qport", bob, channel)

    env.process(alice.run("qport"))
    env.run(until=(num_pulses + 50) * 1e-9)
    bob._process_bin_pairs()


    delay = channel.compute_delay()
    bin_delay = round(delay / 1e-9)

    alice_key = {}
    current_bin = 0
    for bit, is_decoy in alice.bit_log:
        for i in range(2):
            if is_decoy or bit is None:
                current_bin += 1
                continue
            if (bit == 0 and i == 0) or (bit == 1 and i == 1):
                alice_key[current_bin + bin_delay] = bit
            current_bin += 1


    bob_key = {t: b for t, b in bob.sifted_key}
    common = set(alice_key) & set(bob_key)
    errors = sum(1 for t in common if alice_key[t] != bob_key[t])
    qber = errors / len(common) if common else 0
    sim_time = (num_pulses + 10) * 1e-9
    sifted_key_rate = len(common) / sim_time
    asym_key_rate=key_rate.compute_key_rate(qber, sifted_key_rate)
    return qber, asym_key_rate
    
    print("Alice pulses sent:", num_pulses * 2)
    print("Bob sifted bits  :", len(bob.sifted_key))
    print("Matched key bits :", sorted(common))
    print("QBER             :", qber)
    print("Raw Key Rate     : {:.2f} bits/sec".format(rate))
    print("\n--- Bit mismatches ---")
    for t in sorted(common):
        if alice_key[t] != bob_key[t]:
            print(f"Mismatch at bin {t}: Alice={alice_key[t]}, Bob={bob_key[t]}")

    if not bob.check_security():
        print("Protocol aborted due to high DM2 counts.")
  
  
  
env = simpy.Environment()       
def node_factory(name, role, env, **kwargs):
    if role == "Sender":
        return Alice(name, env, num_pulses=kwargs.get("num_pulses", 1000), decoy_prob=kwargs.get("decoy_prob", 0.1))
    elif role == "Receiver":
        snspd = SNSPD(
            efficiency=kwargs.get("efficiency", 0.9),
            dark_count_rate=kwargs.get("dark_count_rate", 10),
            dead_time=kwargs.get("dead_time", 30e-9),
            timing_jitter=kwargs.get("timing_jitter", 30e-12)
        )
        return Bob(name, env, snspd)
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
