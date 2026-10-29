% Ogata, Modern Control Engineering (4th ed.) - MATLAB Program 5-16  (Figure 5-33)
% Response to an initial condition  |  الاستجابة للشروط الابتدائية
t = 0:0.05:3;
A = [0 1;-10 -5];
B = [0;0];
C = [0 0];
D = [0];
[y,x] = initial(A,B,C,D,[2;1],t);
x1 = [1 0]*x';
x2 = [0 1]*x';
plot(t,x1,'o',t,x1,t,x2,'x',t,x2)
grid
title('Response to Initial Condition')
xlabel('t Sec')
ylabel('State Variables x1 and x2')
gtext('x1')
gtext('x2')
