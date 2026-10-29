% Ogata, Modern Control Engineering (4th ed.) - MATLAB Program 6-2  (Figure 6-17)
num = [0 0 0 0 1];
den = [1 1.1 10.3 5 0];
r = rlocus(num,den);
plot(r,'o')
v = [-6 6 -6 6]; axis(v)
grid
title('Root-Locus Plot of G(s) = K/[s(s + 0.5)(s^2 + 0.6s + 10)]')
xlabel('Real Axis')
ylabel('Imag Axis')
