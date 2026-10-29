%% Weeks 15-17 - Root locus technique  |  المحل الهندسي للجذور
% Click on the locus in the figure to read K, damping and wn
% انقر على المنحني لمعرفة قيمة الكسب K ونسبة الإخماد
clc; clear; close all

G = tf(1, conv([1 0], conv([1 1], [1 2])))    % G(s) = 1/(s(s+1)(s+2))
rlocinfo(G)          % قواعد الرسم: الخطوط المقاربة ونقاط الانفصال
rlocus(G)
sgrid(0.5, [])       % خط نسبة إخماد 0.5

%% Design: K for damping ratio 0.5  |  تصميم: إيجاد K لنسبة إخماد 0.5
zeta = 0.5;
[r, K] = rlocus(G, linspace(0, 6, 6001));
best = 0; err = inf;
for i = 2:length(K)
    p = r(:, i);
    [~, idx] = max(imag(p));
    d = -real(p(idx)) / abs(p(idx));
    if abs(d - zeta) < err
        err = abs(d - zeta); best = K(i);
    end
end
fprintf('K for zeta = 0.5  ->  K = %.4f\n', best);
T = feedback(best*G, 1);
figure; step(T)
S = stepinfo(T)

%% Effect of adding a zero  |  تأثير إضافة صفر
figure
rlocus(tf([1 3], conv([1 0], conv([1 1], [1 2]))))
title('Root locus after adding a zero at s = -3')
