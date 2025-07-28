import math

def binary_entropy(q):
    """Binary Shannon entropy."""
    if q <= 0 or q >= 1:
        return 0
    return -q * math.log2(q) - (1 - q) * math.log2(1 - q)

def compute_key_rate(qber, sifted_rate=0.5):
    """
    Computes asymptotic key rate given QBER and sifted key rate. 
    Highly idealistic, assumes an infinite no of pulses
    
    Args:
        qber (float): Quantum Bit Error Rate (0 ≤ qber ≤ 1)
        sifted_rate (float): Fraction of signals that contribute to raw key bits
    
    Returns:
        float: Secret key rate (bits per pulse)
    """
    h = binary_entropy(qber)
    key_rate = sifted_rate * max(0, 1 - 2 * h)
    return round(key_rate, 6)
