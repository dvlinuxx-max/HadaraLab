%% Weeks 18-20 - Polar plot and Nyquist diagram  |  المخطط القطبي ومخطط نايكوست
clc; clear; close all

%% Polar plot: G(jw) for w from 0 to infinity  |  المخطط القطبي
G = tf(1, [0.5 1.5 1])                   % 1 / ((s+1)(0.5s+1))
w = logspace(-2, 2, 500);
H = zeros(size(w));
for k = 1:length(w)
    H(k) = evalfr(G, 1i*w(k));
end
plot(real(H), imag(H), 'LineWidth', 2); grid on; hold on
plot(real(H(1)), imag(H(1)), 'go')      % w = 0
plot(0, 0, 'r+')                         % w -> infinity
hold off
axis equal
title('Polar plot of G(j\omega)')
xlabel('Re\{G(j\omega)\}'); ylabel('Im\{G(j\omega)\}')

% magnitude and phase at a few frequencies
for wi = [0.1 1 2 10]
    g = evalfr(G, 1i*wi);
    fprintf('w = %5.1f :  |G| = %.4f   phase = %7.2f deg\n', wi, abs(g), angle(g)*180/pi);
end

%% Nyquist stability criterion  |  معيار نايكوست للاستقرارية
% Z = N + P   (P = open-loop RHP poles, N = clockwise encirclements of -1)
L1 = tf(2, conv([1 1], [1 2 2]));        % does not encircle -1 -> stable
L2 = tf(20, conv([1 1], [1 2 2]));       % encircles -1 twice   -> unstable
figure; nyquist(L1); title('Nyquist: K = 2 (stable)')
figure; nyquist(L2); title('Nyquist: K = 20 (unstable)')
fprintf('\nClosed loop with K = 2 : stable = %d\n', isstable(feedback(L1, 1)));
fprintf('Closed loop with K = 20: stable = %d\n', isstable(feedback(L2, 1)));
routh([1 3 4 2+20])
