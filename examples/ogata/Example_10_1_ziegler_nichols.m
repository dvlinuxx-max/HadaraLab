% Ogata, Modern Control Engineering - Example 10-1 (Ziegler-Nichols, second method)
% G(s) = 1 / (s (s + 1)(s + 5))     -> book: Kcr = 30, Pcr = 2.8099
% PID:  Kp = 0.6 Kcr = 18,  Ti = 0.5 Pcr = 1.405,  Td = 0.125 Pcr = 0.35124
% ضبط متحكم PID بطريقة زيغلر-نيكولز الثانية
num = [0 0 0 1];
den = [1 6 5 0];
G = tf(num, den);

routh(den + [0 0 0 30])        % K = Kcr = 30 makes a row of zeros (sustained oscillation)
zntune(G, 'PID')
[Kp, Ti, Td, Gc] = zntune(G, 'PID');

T = feedback(Gc*G, 1);
t = 0:0.01:6;
step(T, 6)
grid
title('Unit-Step Response of PID-Controlled System (Ziegler-Nichols)')
S = stepinfo(T)
% Book: maximum overshoot about 62% (fine tuning is then needed - see Program 10-2)
