% Ogata, Modern Control Engineering (4th ed.) - MATLAB Program 6-3  (Figure 6-18)
% --------- Root-locus plot ---------
num = [0 0 0 0 1];
den = [1 1.1 10.3 5 0];
K1 = 0:0.2:20;
K2 = 20:0.1:30;
K3 = 30:5:1000;
K = [K1 K2 K3];
r = rlocus(num,den,K);
plot(r, 'o')
v = [-4 4 -4 4]; axis(v)
grid
title('Root-Locus Plot of G(s) = K/[s(s + 0.5)(s^2 + 0.6s + 10)]')
xlabel('Real Axis')
ylabel('Imag Axis')
