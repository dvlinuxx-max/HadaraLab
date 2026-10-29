% Ogata, Modern Control Engineering (4th ed.) - MATLAB Program 5-4  (Figure 5-20)
% ------------- Unit-step response -------------
% ***** Enter the numerator and denominator of the transfer
% function *****
num = [0 0 25];
den = [1 4 25];
% ***** Enter the following step-response command *****
step(num,den)
% ***** Enter grid and title of the plot *****
grid
title('Unit-Step Response of G(s) = 25/(s^2+4s+25)')
