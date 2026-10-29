%% Weeks 11-12 - P, PI, PD and PID controllers
% مقارنة المتحكمات على النظام  G(s) = 1/(s^2 + 10 s + 20)
% (Open the PID Tuner from the toolbar for interactive tuning)
clc; clear; close all

G = tf(1, [1 10 20]);
T0 = feedback(G, 1);

Cp   = pid(300);              % P
Cpd  = pid(300, 0, 10);       % PD
Cpi  = pid(30, 70);           % PI
Cpid = pid(350, 300, 50);     % PID

Tp   = feedback(Cp*G, 1);
Tpd  = feedback(Cpd*G, 1);
Tpi  = feedback(Cpi*G, 1);
Tpid = feedback(Cpid*G, 1);

step(T0, Tp, Tpd, Tpi, Tpid, 2)
legend('No controller', 'P', 'PD', 'PI', 'PID')
title('Closed-loop step response with different controllers')

% compare the specifications  |  مقارنة المواصفات
Sp = stepinfo(Tp); Spd = stepinfo(Tpd); Spi = stepinfo(Tpi); Spid = stepinfo(Tpid);
fprintf('\n  Controller   Overshoot(%%)   Settling(s)   DC gain\n');
fprintf('  P            %8.2f      %8.3f    %6.3f\n', Sp.Overshoot, Sp.SettlingTime, dcgain(Tp));
fprintf('  PD           %8.2f      %8.3f    %6.3f\n', Spd.Overshoot, Spd.SettlingTime, dcgain(Tpd));
fprintf('  PI           %8.2f      %8.3f    %6.3f\n', Spi.Overshoot, Spi.SettlingTime, dcgain(Tpi));
fprintf('  PID          %8.2f      %8.3f    %6.3f\n', Spid.Overshoot, Spid.SettlingTime, dcgain(Tpid));
