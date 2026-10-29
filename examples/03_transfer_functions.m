%% Weeks 3-6 - Transfer functions, poles & zeros, DC servo motor
% دالة التحويل، الأقطاب والأصفار، ونموذج محرك التيار المستمر
clc; clear; close all

%% Method 1: coefficients  |  الطريقة الأولى: المعاملات
num = [1 3];
den = [1 4 8 0];
G1 = tf(num, den)

%% Method 2: the Laplace variable s  |  الطريقة الثانية: المتغير s
s = tf('s');
G2 = (s + 3) / (s * (s^2 + 4*s + 8))

%% Method 3: zeros, poles and gain  |  الطريقة الثالثة: الأصفار والأقطاب
G3 = zpk([-3], [0 -2+2i -2-2i], 1)

%% Poles and zeros  |  الأقطاب والأصفار
p = pole(G1)
z = zero(G1)
pzmap(G1)

%% DC servo motor model (armature controlled)  |  نموذج محرك DC
% speed(s)/V(s) = K / ( (J s + b)(L s + R) + K^2 )
J = 0.01;   % moment of inertia   عزم القصور الذاتي
b = 0.1;    % friction            معامل الاحتكاك
K = 0.01;   % motor constant      ثابت المحرك
R = 1;      % resistance          المقاومة
L = 0.5;    % inductance          المحاثة
P_speed = tf(K, conv([J b], [L R]) + [0 0 K^2])     % السرعة / الجهد
P_pos   = P_speed * tf(1, [1 0])                      % الموقع / الجهد
figure
step(P_speed)
title('DC motor speed response to 1 V')
damp(P_speed)
