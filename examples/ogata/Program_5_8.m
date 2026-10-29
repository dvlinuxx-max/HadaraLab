% Ogata, Modern Control Engineering (4th ed.) - MATLAB Program 5-8  (Figure 5-24)
num = [0 0 1];
den = [1 0.2 1];
impulse(num,den);
grid
title('Unit-Impulse Response of G(s) = 1/(s^2 + 0.2s + 1)')
