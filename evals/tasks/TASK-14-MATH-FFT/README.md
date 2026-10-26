# Task Specification: Cooley-Tukey Radix-2 1D Fast Fourier Transform

## 1. Function Contract
Implement `fft_1d` and `ifft_1d` in `src/fft_solver.py`.

### Function Signatures
```python
def fft_1d(x: List[complex]) -> List[complex]:
def ifft_1d(X: List[complex]) -> List[complex]:
```
- Computes Discrete Fourier Transform $X_k = \sum_{n=0}^{N-1} x_n e^{-i 2\pi k n / N}$ using Cooley-Tukey Radix-2 algorithm.
- Input length $N$ must be a power of 2 ($N = 2^p$). If not, raise `ValueError("Input length must be a power of 2")`.
- `ifft_1d` satisfies Parseval and invertibility: `ifft_1d(fft_1d(x)) == x` within numerical tolerance $10^{-10}$.
