%% Weeks 21-29 - Lead compensator design  |  تصميم المعوض المتقدم (Lead)
% Ogata, chapter 7: plant G(s) = 4 / (s (s + 2))
% Requirements: Kv = 20 s^-1, phase margin >= 50 deg
clc; clear; close all

G = tf(4, [1 2 0])
[Gm0, Pm0] = margin(G);
fprintf('Uncompensated phase margin = %.1f deg\n', Pm0);

% Step 1: gain for the static velocity error constant  Kv = lim s*K*G(s) = 2K
K = 10;
[Gm1, Pm1] = margin(K*G);
fprintf('With K = %d : phase margin = %.1f deg\n', K, Pm1);

% Step 2: required phase lead (+5 deg safety margin)
phi_m = (50 - Pm1 + 5) * pi / 180;
alpha = (1 - sin(phi_m)) / (1 + sin(phi_m));
fprintf('Required lead = %.1f deg,  alpha = %.4f\n', phi_m*180/pi, alpha);

% Step 3: new crossover where |K G(jw)| = sqrt(alpha)
f = @(w) abs(evalfr(K*G, 1i*w)) - sqrt(alpha);
wm = fzero(f, [0.1 100]);
T = 1 / (wm * sqrt(alpha));
fprintf('New crossover wm = %.3f rad/s,  T = %.4f\n', wm, T);

% Step 4: the compensator
Gc = K * tf([T 1], [alpha*T 1])
L = Gc * G;
margin(L)

figure
step(feedback(K*G, 1), feedback(L, 1), 4)
legend('Gain only (K = 10)', 'With lead compensator')
