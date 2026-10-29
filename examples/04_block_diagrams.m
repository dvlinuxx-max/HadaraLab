%% Weeks 7-8 - Block diagram reduction  |  تبسيط المخططات الصندوقية
clc; clear; close all

G1 = tf(1, [1 1]);
G2 = tf(2, [1 3]);
H  = tf(1, [1 5]);

Ts = series(G1, G2)          % توالي:   G1*G2
Tp = parallel(G1, G2)        % توازي:   G1+G2
Tf = feedback(G1*G2, H)      % تغذية عكسية سالبة: G/(1+GH)
Tpos = feedback(G1, H, +1)   % تغذية عكسية موجبة

% Reduction of a two-loop system  |  نظام بحلقتين
inner = feedback(G2, H);     % الحلقة الداخلية أولاً
T = feedback(G1 * inner, 1)  % ثم الحلقة الخارجية
T = minreal(T)               % حذف الأقطاب والأصفار المشتركة

step(T); grid on
title('Overall closed-loop step response')
