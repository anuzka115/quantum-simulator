import sys
import os
import numpy as np

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Hardware.node import Node
from Hardware.gates import H, CX
from Hardware.state import QuantumState
class EntanglementManager:
    '''Creates Bell pairs and distributes among 2 nodes. The global state is known by both nodes, but depending on 
    whether it's node A or B the measurement will be different. Future work: extend to GHZ(n_qubits) to distribute among
    n nodes.'''
    def __init__(self):
        self.entangled_pairs = {}  # key: pair_id, value: (state_vector, node_A, node_B)

    def create_bell_pair(self, node_a:Node, node_b: Node, bell_type='00'):
        
        basis_states = {
            '00': np.array([1, 0, 0, 0], dtype=complex),
            '01': np.array([0, 1, 0, 0], dtype=complex),
            '10': np.array([0, 0, 1, 0], dtype=complex),
            '11': np.array([0, 0, 0, 1], dtype=complex)
        }
        state = basis_states[bell_type]
        H_I = np.kron(H, np.eye(2, dtype=complex)) #HI
        state = H_I @ state
        state = CX @ state
        shared_state = QuantumState(ket=state)
        pair_id = f"{node_a.node_id}_{node_b.node_id}_{len(self.entangled_pairs)}"
        self.entangled_pairs[pair_id] = (shared_state, node_a, node_b)

        node_a.receive_entangled_qubit(shared_state, qubit_index=0, pair_id=pair_id)
        node_b.receive_entangled_qubit(shared_state, qubit_index=1, pair_id=pair_id)

        return pair_id, state

