%% Weeks 9-10 - Time-domain analysis & steady-state error
% تحليل الاستجابة الزمنية للنظام من الدرجة الثانية والخطأ في الحالة المستقرة
clc; clear; close all

%% Second-order system  wn^2 / (s^2 + 2 zeta wn s + wn^2)
wn = 2;
figure; hold on
for zeta = [0.1 0.3 0.5 0.7 1.0]
    G = tf(wn^2, [1 2*zeta*wn wn^2]);
    step(G, 8)
end
hold off
legend('\zeta = 0.1', '\zeta = 0.3', '\zeta = 0.5', '\zeta = 0.7', '\zeta = 1.0')
title('Effect of damping ratio on the step response')

%% Specifications  |  مواصفات الاستجابة
zeta = 0.5;
G = tf(wn^2, [1 2*zeta*wn wn^2])
S = stepinfo(G)                 % من المحاكاة
F = stepspecs(zeta, wn)         % من القوانين النظرية (Ogata)

%% Steady-state error  |  الخطأ في الحالة المستقرة
% Type 0 and Type 1 open-loop systems with unity feedback
G0 = tf(10, [1 3 2]);           % type 0
G1 = tf(10, [1 3 2 0]);         % type 1
ess(G0)
ess(G1)
figure
ramp(feedback(G1, 1), 10)
title('Ramp response of a type-1 system: finite error = 1/Kv')
