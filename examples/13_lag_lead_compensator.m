%% Weeks 21-29 - Lag-lead compensator  |  المعوض المتأخر-المتقدم (Lag-Lead)
% Ogata, chapter 7: plant G(s) = K / (s (s + 1)(s + 2))
% Requirements: Kv = 10 s^-1, phase margin = 50 deg, gain margin >= 10 dB
% الجزء المتقدم (Lead) يرفع هامش الطور، والجزء المتأخر (Lag) يحسن الخطأ
clc; clear; close all

G = tf(1, conv([1 0], conv([1 1], [1 2])));
K = 20;                                   % Kv = K/2 = 10
[Gm0, Pm0] = margin(K*G);
fprintf('Gain only (K = 20): Pm = %.1f deg  -> unstable\n', Pm0);

% New gain crossover chosen at w = 1.5 rad/s (near the -180 deg frequency)
lag  = tf([1 0.15], [1 0.015]);           % zero at 0.15, pole at 0.015 (beta = 10)
lead = tf([1 0.7],  [1 7]);               % zero at 0.7,  pole at 7
Gc = lead * lag
L = K * Gc * G;

% Ogata designs this with asymptotic Bode approximations (target Pm = 50 deg);
% the exact computation below gives Pm ~ 55 deg and Gm ~ 17 dB, so it meets the spec.
% الكتاب يستخدم التقريب البياني، والحساب الدقيق يعطي هامش طور أكبر قليلاً
[Gm, Pm, Wcg, Wcp] = margin(L);
fprintf('Compensated: Pm = %.1f deg at %.2f rad/s,  Gm = %.1f dB\n', Pm, Wcp, 20*log10(Gm));
fprintf('Kv = %.2f\n', dcgain(tf([1 0], 1) * L));
margin(L)

figure
bode(K*G, L)
legend('Uncompensated (K = 20)', 'Lag-lead compensated')

figure
step(feedback(L, 1), 20)
title('Closed-loop step response with lag-lead compensator')
S = stepinfo(feedback(L, 1))
