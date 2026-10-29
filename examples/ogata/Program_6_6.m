% Ogata, Modern Control Engineering (4th ed.) - MATLAB Program 6-6  (Figure 6-23)
% Constant zeta lines and constant wn circles  |  خطوط نسبة الإخماد ودوائر التردد الطبيعي
num = [0 0 0 1];
den = [1 4 5 0];
rlocus(num, den);
v = [-3 1 -2 2]; axis(v); axis('square')
sgrid([0.5,0.707], [0.5,1,2])
title('Root-Locus Plot with \zeta = 0.5 and 0.707 Lines and \omega_n = 0.5, 1, and 2 Circles')
gtext('\zeta = 0.5')
gtext('\zeta = 0.707')
gtext('\omega_n = 2')
gtext('\omega_n = 1')
gtext('\omega_n = 0.5')
% Labels from gtext appear on the plot - drag them to place them like the book.
