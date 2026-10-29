%% Lab - State-space models  |  نماذج فضاء الحالة
clc; clear; close all

% Mass-spring-damper:  m x'' + b x' + k x = F
m = 1; b = 2; k = 5;
A = [0 1; -k/m -b/m];
B = [0; 1/m];
C = [1 0];
D = 0;

eigenvalues = eig(A)            % = poles of the system
G = ss(A, B, C, D)              % converted to a transfer function
[num, den] = ss2tf(A, B, C, D)
[A2, B2, C2, D2] = tf2ss(num, den)

step(G); title('Mass-spring-damper: step response')

% Free response with ode45  |  الاستجابة الحرة بحل المعادلة التفاضلية
f = @(t, x) A*x;
[t, x] = ode45(f, [0 6], [1; 0]);
figure
plot(t, x(:, 1), t, x(:, 2), 'LineWidth', 2); grid on
legend('position x', 'velocity v')
title('Initial-condition response (x0 = 1)')
