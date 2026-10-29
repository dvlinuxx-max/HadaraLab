%% Weeks 13-14 - Routh-Hurwitz stability criterion  |  معيار راوث
clc; clear; close all

%% Example 1: unstable system  |  نظام غير مستقر
p1 = [1 2 3 4 5];
routh(p1)
roots(p1)

%% Example 2: zero in the first column  |  صفر في العمود الأول
p2 = [1 2 2 4 1 1];
routh(p2)

%% Example 3: row of zeros (imaginary-axis roots)  |  صف كامل أصفار
p3 = [1 0 5 0 4];
routh(p3)

%% Example 4: range of K for stability  |  مدى K الذي يحقق الاستقرارية
% Characteristic equation: s^3 + 3 s^2 + 2 s + K = 0
G = tf(1, [1 3 2 0]);
krange(G)
for K = [2 6 10]
    p = [1 3 2 K];
    fprintf('K = %2d :  roots = %s\n', K, mat2str(roots(p)', 3));
end
step(feedback(2*G, 1), feedback(6*G, 1), 30)
legend('K = 2 (stable)', 'K = 6 (marginal)')
