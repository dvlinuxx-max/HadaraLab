% Ogata, Modern Control Engineering (4th ed.) - MATLAB Program 3-3
% State space -> transfer function  |  تحويل فضاء الحالة إلى دالة تحويل
A = [0 1 0; 0 0 1; -5 -25 -5];
B = [0; 25; -120];
C = [1 0 0];
D = [0];
[num,den] = ss2tf(A,B,C,D)
% ***** The same result can be obtained by entering the following command *****
[num,den] = ss2tf(A,B,C,D,1)
