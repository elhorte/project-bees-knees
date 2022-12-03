% FFT noodling around

clc
clearvars

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% load signal
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


%Fs = 192000;           % Sampling frequency     
Fs = 192000;            % Sampling frequency       
T = 1/Fs;               % Sampling period       
L = 1500;               % Length of signal (msec)
t = (0:L-1)*T;          % Time vector

%audiopath = 'C:\Users\jamie\Desktop\';
audiopath = '';
%Dropbox = 'C:\Users\jamie\Dropbox (Personal)\dev\Enterprise Neurosystems\MatLab\';
audio_bees = 'Audio_192k16b_12min_in_for_2min.wav';
audio_squarewave_2k = 'squarewave_2k.wav';
audio_sinewave_2k = 'sinewave_2k.wav';
source = audio_bees;
audiosource = strcat(audiopath, source);

%[X, Fs] = audioread(audiosource);

% generate two sinewaves at 50Hz and 120Hz
%S = 0.7*sin(2*pi*50*t) + sin(2*pi*120*t);
% make some noise
%X = S + 2*randn(size(t));

%n = 2^nextpow2(size(X,1));
%n = 32768;

%% data
[signal,Fs] = audioread(audiosource);

[samples,channels] = size(audiosource);
channels = 1;

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% FFT parameters
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
NFFT = 4096;    % 
OVERLAP = 0.75;

% spectrogram dB scale
spectrogram_dB_scale = 80;  % dB range scale (means , the lowest displayed level is XX dB below the max level)

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% options 
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% if you are dealing with acoustics, you may wish to have A weighted
% spectrums 

% option_w = 0 : linear spectrum (no weighting dB (L) )
% option_w = 1 : A weighted spectrum (dB (A) )
option_w = 1;

%% decimate (if needed)
% NB : decim = 1 will do nothing (output = input)
decim = 1;
if decim>1
    for ck = 1:channels
    newsignal(:,ck) = decimate(signal(:,ck),decim);
    Fs = Fs/decim;
    end
   signal = newsignal;
end
samples = length(signal);
time = (0:samples-1)*1/Fs;

%%%%%% legend structure %%%%%%%%

for ck = 1:channels
    leg_str{ck} = ['Channel ' num2str(ck) ];
end

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% display 1 : time domain plot
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

figure(1),plot(time,signal);grid on
title(['Time plot  / Fs = ' num2str(Fs) ' Hz ']);
xlabel('Time (s)');ylabel('Amplitude');
legend(leg_str);

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% display 2 : averaged FFT spectrum
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

[freq, sensor_spectrum] = myfft_peak(signal,Fs,NFFT,OVERLAP);

% convert to dB scale (ref = 1)
sensor_spectrum_dB = 20*log10(sensor_spectrum);

% apply A weigthing if needed
if option_w == 1
    pondA_dB = pondA_function(freq);
    sensor_spectrum_dB = sensor_spectrum_dB+pondA_dB;
    my_ylabel = ('Amplitude (dB (A))');
else
    my_ylabel = ('Amplitude (dB (L))');
end


figure(2),plot(freq,sensor_spectrum_dB);grid on
df = freq(2)-freq(1); % frequency resolution 
title(['Averaged FFT Spectrum  / Fs = ' num2str(Fs) ' Hz / Delta f = ' num2str(df,3) ' Hz ']);
xlabel('Frequency (Hz)');ylabel(my_ylabel);
legend(leg_str);

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% display 3 : time / frequency analysis : spectrogram demo
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

for ck = 1:channels
    [sg,fsg,tsg] = specgram(signal(:,ck),NFFT,Fs,hanning(NFFT),floor(NFFT*OVERLAP));  

    % FFT normalisation and conversion amplitude from linear to dB (peak)
    sg_dBpeak = 20*log10(abs(sg))+20*log10(2/length(fsg));     % NB : X=fft(x.*hanning(N))*4/N; % hanning only

    % apply A weigthing if needed
    if option_w == 1
        pondA_dB = pondA_function(fsg);
        sg_dBpeak = sg_dBpeak+(pondA_dB*ones(1,size(sg_dBpeak,2)));
        my_title = ('Spectrogram (dB (A))');
    else
        my_title = ('Spectrogram (dB (L))');
    end

    % saturation of the dB range : 
    % saturation_dB = 60;  % dB range scale (means , the lowest displayed level is XX dB below the max level)
    min_disp_dB = round(max(max(sg_dBpeak))) - spectrogram_dB_scale;
    sg_dBpeak(sg_dBpeak<min_disp_dB) = min_disp_dB;

    % plots spectrogram
    figure(2+ck);
    imagesc(tsg,fsg,sg_dBpeak);colormap('jet');
    axis('xy');colorbar('vert');grid on
    df = fsg(2)-fsg(1); % freq resolution 
    title([my_title ' / Fs = ' num2str(Fs) ' Hz / Delta f = ' num2str(df,3) ' Hz / Channel : ' num2str(ck)]);
    xlabel('Time (s)');ylabel('Frequency (Hz)');

end

function pondA_dB = pondA_function(f)
	% dB (A) weighting curve
	n = ((12200^2*f.^4)./((f.^2+20.6^2).*(f.^2+12200^2).*sqrt(f.^2+107.7^2).*sqrt(f.^2+737.9^2)));
	r = ((12200^2*1000.^4)./((1000.^2+20.6^2).*(1000.^2+12200^2).*sqrt(1000.^2+107.7^2).*sqrt(1000.^2+737.9^2))) * ones(size(f));
	pondA = n./r;
	pondA_dB = 20*log10(pondA(:));
end


function  [freq_vector,fft_spectrum] = myfft_peak(signal, Fs, nfft, Overlap)
% FFT peak spectrum of signal  (example sinus amplitude 1   = 0 dB after fft).
% Linear averaging
%   signal - input signal, 
%   Fs - Sampling frequency (Hz).
%   nfft - FFT window size
%   Overlap - buffer percentage of overlap % (between 0 and 0.95)

[samples,channels] = size(signal);

% fill signal with zeros if its length is lower than nfft
if samples<nfft
    s_tmp = zeros(nfft,channels);
    s_tmp((1:samples),:) = signal;
    signal = s_tmp;
    samples = nfft;
end

% window : hanning
window = hanning(nfft);
window = window(:);

%    compute fft with overlap 
offset = fix((1-Overlap)*nfft);
spectnum = 1+ fix((samples-nfft)/offset); % Number of windows
%     % for info is equivalent to : 
%     noverlap = Overlap*nfft;
%     spectnum = fix((samples-noverlap)/(nfft-noverlap));	% Number of windows

    % main loop
    fft_spectrum = 0;
    for i=1:spectnum
        start = (i-1)*offset;
        sw = signal((1+start):(start+nfft),:).*(window*ones(1,channels));
        fft_spectrum = fft_spectrum + (abs(fft(sw))*4/nfft);     % X=fft(x.*hanning(N))*4/N; % hanning only 
    end
    fft_spectrum = fft_spectrum/spectnum; % to do linear averaging scaling

    % one sidded fft spectrum  % Select first half 
    if rem(nfft,2)    % nfft odd
        select = (1:(nfft+1)/2)';
    else
        select = (1:nfft/2+1)';
    end

fft_spectrum = fft_spectrum(select,:);
freq_vector = (select - 1)*Fs/nfft;

end

