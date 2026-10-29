% Ogata, Modern Control Engineering (4th ed.) - MATLAB Program 8-8  (Figure 8-40)
% ---------- Nyquist plot ----------
num = [0 0 1];
den = [1 1 0];
nyquist(num,den)
v = [-2 2 -5 5]; axis(v)
grid
title('Nyquist Plot of G(s) = 1/[s(s + 1)]')
