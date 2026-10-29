% Ogata, Modern Control Engineering (4th ed.) - MATLAB Program 6-1  (Figure 6-34)
% Conditionally stable system  |  نظام مستقر شرطياً
num = [0 0 0 1 2 4];
den = conv(conv([1 4 0],[1 6]), [1 1.4 1]);
rlocus(num, den)
v = [-7 3 -5 5]; axis(v); axis('square')
grid
title('Root-Locus Plot of G(s) = K(s^2+ 2s + 4)/[s(s + 4)(s + 6)(s^2 + 1.4s + 1)]')
text(1.0, 0.55,'K = 12')
text(1.0, 3.0,'K = 73')
text(1.0, 4.15,'K = 154')
