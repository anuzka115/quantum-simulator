import numpy as np
import simpy
import sys
import os


# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Hardware.node import Node
from utils.entanglement_manage import EntanglementManager
from utils import key_rate
# ————————————————
# Helper: projective measurement of one qubit in a 2-qubit density matrix
# along direction φ in the x–z plane
# ————————————————
def measure_local(rho, qubit_index, phi):
    # Pauli matrices
    Z = np.array([[1, 0], [0, -1]], complex)
    X = np.array([[0, 1], [1, 0]], complex)
    # operator n·σ
    n = np.cos(phi)*Z + np.sin(phi)*X

    # single-qubit +/− projectors
    Pp = (np.eye(2) + n) / 2
    Pm = (np.eye(2) - n) / 2

    I2 = np.eye(2, dtype=complex)
    if qubit_index == 0:
        Pp_full = np.kron(Pp,  I2)
        Pm_full = np.kron(Pm,  I2)
    else:
        Pp_full = np.kron(I2, Pp)
        Pm_full = np.kron(I2, Pm)

    p_plus = np.real(np.trace(Pp_full @ rho))
    if np.random.rand() < p_plus:
        outcome = +1
        rho_post = (Pp_full @ rho @ Pp_full) / (p_plus + 1e-16)
    else:
        outcome = -1
        rho_post = (Pm_full @ rho @ Pm_full) / ((1 - p_plus) + 1e-16)

    return outcome, rho_post

# ————————————————
# Alice drives the entanglement creation & measurement
# ————————————————
class Alice(Node):
    def __init__(self, node_id, env, num_pulses,
                 p_depol=0.02,      # 2% state depolarization
                 misalign_deg=1.0,  # 1° basis misalignment
                 p_flip=0.005       # 0.5% detector flip
                ):
        super().__init__(node_id, env)
        self.num_pulses = num_pulses
        self.p_depol     = p_depol
        self.misalign   = np.deg2rad(misalign_deg)
        self.p_flip     = p_flip

        # storage of raw results
        self.phi_list = []
        self.s_list   = []

    def run(self, manager, bob):
        angles_a = [0, np.pi/4, np.pi/2]
        angles_b = [np.pi/4, np.pi/2, 3*np.pi/4]
        I4 = np.eye(4, dtype=complex)

        for _ in range(self.num_pulses):
            # 1) Create fresh Bell pair
            pair_id, _ = manager.create_bell_pair(self, bob, bell_type='00')
            shared_state, _, _ = manager.entangled_pairs[pair_id]

            # overwrite to |Ψ⁻> = (|01> - |10>)/√2
            psi_minus = np.array([0, 1, -1, 0], complex)/np.sqrt(2)
            rho_psi   = np.outer(psi_minus, psi_minus.conj())

            # 2) Mix with white noise → Werner state
            I4 = np.eye(4, dtype=complex)  # 4x4 identity for two qubits

            rho = (1 - self.p_depol) * rho_psi + self.p_depol * (I4 / 4)


            # 3) Pick random ideal angles
            φa = np.random.choice(angles_a)
            φb = np.random.choice(angles_b)

            # 4) Apply misalignment noise
            φa_m = φa + np.random.normal(0, self.misalign)
            φb_m = φb + np.random.normal(0, self.misalign)

            # 5) Measure qubit 0 (Alice) then qubit 1 (Bob)
            sa, rho1 = measure_local(rho,      qubit_index=0, phi=φa_m)
            sb, _    = measure_local(rho1,     qubit_index=1, phi=φb_m)

            # 6) Detector flip errors
            if np.random.rand() < self.p_flip:
                sa = -sa
            if np.random.rand() < self.p_flip:
                sb = -sb

            # 7) Record raw data
            self.phi_list.append(φa)
            self.s_list.append(sa)
            bob.phi_list.append(φb)
            bob.s_list.append(sb)

            yield self.env.timeout(0)  # no real time delay

# ————————————————
# Bob only needs storage
# ————————————————
class Bob(Node):
    def __init__(self, node_id, env):
        super().__init__(node_id, env)
        self.phi_list = []
        self.s_list   = []


def run_e91(alice, bob, channel, env, num_pulses=10000):
   
    
    manager = EntanglementManager()

    env.process(alice.run(manager, bob))
    env.run()

    # —— Sift: keep only those rounds with the same nominal angle φa == φb —— 
    # (shared angles: π/4 and π/2)
    alice_key = []
    bob_key   = []
    for φa, φb, sa, sb in zip(alice.phi_list, bob.phi_list,
                              alice.s_list,   bob.s_list):
        if abs(φa - φb) < 1e-8:
            # map ±1 → 0/1
            ba = (sa + 1)//2
            bb = (sb + 1)//2
            # anticorrelation of |Ψ⁻⟩ → Bob flips
            bb = 1 - bb
            alice_key.append(int(ba))
            bob_key.append(int(bb))

   
    #m = min(20, len(alice_key))
    '''print("Alice key (first 20):", alice_key[:m])
    print("Bob   key (first 20):", bob_key[:m])
    print("Sifted key length:", len(alice_key))'''
    if alice_key:
        errors = sum(a!=b for a,b in zip(alice_key, bob_key))
        qber=errors/len(alice_key)
        clock_rate = 10e6  # 10 MHz source
        sim_time = num_pulses / clock_rate 
        #sim_time = (num_pulses + 10) * 1e-9
        sifted_key_rate = len(alice_key) / sim_time
        asym_key_rate=key_rate.compute_key_rate(qber, sifted_key_rate)
        return qber, asym_key_rate
    
    else:
        return None
    
env = simpy.Environment()       
def node_factory(name, role, env, **kwargs):
    if role == "Sender":
        return Alice(name, env, num_pulses=kwargs.get("num_pulses", 10000), p_depol=kwargs.get("p_depol", 0.03), misalign_deg=kwargs.get("misalign_deg", 1.5), p_flip=kwargs.get("p_flip", 0.01))
    elif role == "Receiver":
        
        return Bob(name, env)
    else:
        return Node(name, env)