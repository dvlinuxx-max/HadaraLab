% Ogata, Modern Control Engineering (4th ed.) - MATLAB Programs 8-1 and 8-2
% (Figures 8-20 and 8-22)
num = [0 0 25];
den = [1 4 25];
bode(num,den)
title('Bode Diagram of G(s) = 25/(s^2 + 4s + 25)')

figure
num = [0 9 1.8 9];
den = [1 1.2 9 0];
bode(num,den)
title('Bode Diagram of G(s) = 9(s^2 + 0.2s + 1)/[s(s^2 + 1.2s + 9)]')
