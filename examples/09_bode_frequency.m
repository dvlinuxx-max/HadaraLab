%% Weeks 18-20 - Frequency response & Bode diagrams  |  مخطط بود
clc; clear; close all

G = tf(10, conv([1 0], conv([1 1], [0.1 1])))   % 10 / ( s (s+1)(0.1s+1) )

bode(G)                         % المقدار والطور
figure
margin(G)                       % هامش الكسب وهامش الطور
[Gm, Pm, Wcg, Wcp] = margin(G);
fprintf('Gm = %.2f dB,  Pm = %.2f deg\n', 20*log10(Gm), Pm);

%% Effect of the gain  |  تأثير الكسب على مخطط بود
figure
bode(tf(1, [1 1]), tf(10, [1 1]), tf(100, [1 1]))
legend('K = 1', 'K = 10', 'K = 100')

%% Nyquist diagram  |  مخطط نايكوست
L = tf(5, conv([1 1], [1 2 2]));
figure
nyquist(L)
bw = bandwidth(feedback(L, 1))
