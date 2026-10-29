%% Weeks 1-2 - Open-loop vs closed-loop systems
% مقارنة نظام الحلقة المفتوحة مع نظام الحلقة المغلقة (تغذية عكسية سالبة)
clc; clear; close all

G = tf(10, [1 3 2])          % دالة تحويل النظام (Plant)
T = feedback(G, 1)           % الحلقة المغلقة: G/(1+G)

% الاستجابة الدرجية للنظامين
step(G, T)
legend('Open loop  G(s)', 'Closed loop  T(s)')

% قيم الحالة المستقرة
dc_open   = dcgain(G)
dc_closed = dcgain(T)

% الحلقة المغلقة أسرع وأقل حساسية للتغيرات لكن يبقى خطأ في الحالة المستقرة
ess_closed = 1 - dc_closed
