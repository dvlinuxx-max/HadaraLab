% Ogata, Modern Control Engineering (4th ed.) - MATLAB Program 7-2
% ---------- Root Locus Plot ----------
% ***** Root locus plots of the compensated system and
% uncompensated system *****
% ***** Enter the numerators and denominators of the
% compensated and uncompensated systems *****
numc = [0 0 0 1 0.05];
denc = [1 3.005 2.015 0.01 0];
num = [0 0 0 1.06];
den = [1 3 2 0];
% ***** Enter rlocus command. Plot the root loci of both
% systems *****
rlocus(numc,denc)
hold
rlocus(num,den)
v = [-3 1 -2 2]; axis(v); axis('square')
grid
text(-2.8,0.2,'Compensated system')
text(-2.8,1.2,'Uncompensated system')
text(-2.8,0.58,'Original closed-loop pole')
text(-0.1,0.85,'New closed-')
text(-0.1,0.62,'loop pole')
title('Root-Locus Plots of Compensated and Uncompensated Systems')
hold
