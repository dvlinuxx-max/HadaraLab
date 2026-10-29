%% Week 1 - MATLAB basics  |  أساسيات الماتلاب
% المتغيرات، المصفوفات، العمليات، والرسم البياني
clc; clear; close all

%% Variables and arithmetic  |  المتغيرات والعمليات الحسابية
a = 5
b = 3;
c = a^2 + sqrt(b)          % عند حذف الفاصلة المنقوطة تظهر النتيجة

%% Vectors and matrices  |  المتجهات والمصفوفات
v = [1 2 3 4 5]            % متجه صفي
w = (1:5)'                 % متجه عمودي
A = [4 -2; 1 1]
B = A'                     % المنقول
C = A * B                  % ضرب مصفوفات
D = A .* B                 % ضرب عنصر بعنصر
detA = det(A)
invA = inv(A)
lambda = eig(A)            % القيم الذاتية

%% Polynomials  |  كثيرات الحدود
p = [1 6 11 6];            % s^3 + 6s^2 + 11s + 6
r = roots(p)               % الجذور
p2 = poly(r)               % استرجاع كثيرة الحدود من الجذور
q = conv([1 1], [1 2])     % (s+1)(s+2)

%% Loops and conditions  |  الحلقات والشروط
total = 0;
for k = 1:10
    total = total + k;
end
fprintf('Sum of 1..10 = %d\n', total);
if total > 50
    disp('Total is greater than 50')
else
    disp('Total is 50 or less')
end

%% Plotting  |  الرسم
t = linspace(0, 2*pi, 200);
plot(t, sin(t), 'b', t, cos(t), 'r--', 'LineWidth', 2)
grid on
title('sin(t) and cos(t)')
xlabel('t (rad)'); ylabel('amplitude')
legend('sin', 'cos')
