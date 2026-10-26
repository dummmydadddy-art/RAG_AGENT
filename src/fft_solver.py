import cmath
from typing import List


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def fft_1d(x: List[complex]) -> List[complex]:
    """
    Cooley-Tukey Radix-2 1D Fast Fourier Transform.
    """
    n = len(x)
    if not _is_power_of_two(n):
        raise ValueError(f"Input length must be a power of 2, got {n}")

    if n <= 1:
        return [complex(val) for val in x]

    # Divide
    even = fft_1d([x[i] for i in range(0, n, 2)])
    odd = fft_1d([x[i] for i in range(1, n, 2)])

    # Combine
    combined = [complex(0)] * n
    for k in range(n // 2):
        factor = cmath.exp(-2j * cmath.pi * k / n) * odd[k]
        combined[k] = even[k] + factor
        combined[k + n // 2] = even[k] - factor

    return combined


def ifft_1d(X: List[complex]) -> List[complex]:
    """
    Inverse 1D Fast Fourier Transform using conjugate duality.
    """
    n = len(X)
    if not _is_power_of_two(n):
        raise ValueError(f"Input length must be a power of 2, got {n}")

    # Conjugate input
    conjugated = [val.conjugate() for val in X]
    transformed = fft_1d(conjugated)
    # Conjugate output and scale by 1/N
    return [(val.conjugate() / n) for val in transformed]
