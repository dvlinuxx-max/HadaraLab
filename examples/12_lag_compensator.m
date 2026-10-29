%% Weeks 21-29 - Lag compensator design  |  تصميم المعوض المتأخر (Lag)
% Ogata, chapter 7: plant G(s) = 1 / (s (s + 1)(0.5 s + 1))
% Requirements: Kv = 5 s^-1, phase margin >= 40 deg, gain margin >= 10 dB
% المعوض المتأخر يحسن الخطأ في الحالة المستقرة بدون ما يخرب الاستقرارية
clc; clear; close all

G = tf(1, conv([1 1 0], [0.5 1]))

% Step 1: gain for Kv = lim s*K*G(s) = K  ->  K = 5
K = 5;
[Gm1, Pm1] = margin(K*G);
fprintf('With K = 5 only : Pm = %.1f deg  (unstable if negative)\n', Pm1);

% Step 2: new gain crossover where the phase of K*G = -180 + Pm + 12 deg
Pm_req = 40;
target = -180 + Pm_req + 12;
ph = @(w) angle(evalfr(K*G, 1i*w)) * 180/pi - 360*(angle(evalfr(K*G, 1i*w)) > 0);
wc = fzero(@(w) ph(w) - target, [0.1 1.5]);
beta = abs(evalfr(K*G, 1i*wc));          % attenuation needed at wc
T = 10 / wc;                             % lag zero one decade below wc
fprintf('New crossover wc = %.3f rad/s,  beta = %.3f,  T = %.2f\n', wc, beta, T);

% Step 3: the lag compensator  Gc(s) = K (T s + 1) / (beta T s + 1)
Gc = K * tf([T 1], [beta*T 1])
L = Gc * G;
figure; margin(L)
[Gm, Pm] = margin(L);
fprintf('Compensated: Pm = %.1f deg, Gm = %.1f dB, Kv = %.2f\n', Pm, 20*log10(Gm), dcgain(tf([1 0], 1) * L));

% Step 4: compare step and ramp responses
figure
step(feedback(L, 1), 40)
title('Closed-loop step response with lag compensator')
figure
ramp(feedback(L, 1), 20)
title('Ramp response: steady-state error = 1/Kv = 0.2')
