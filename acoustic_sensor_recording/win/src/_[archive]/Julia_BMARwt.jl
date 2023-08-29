#!/usr/bin/env julia

using WAV          # For audio file handling, similar to soundfile
using PortAudio    # For audio playback and recording, similar to sounddevice
using Dates        # For datetime functionalities
using DelimitedFiles  # For reading/writing delimited files
using Base.Threads  # For threading
using Distributed  # For multiprocessing
using LinearAlgebra, FFTW  # For various numerical operations
using Plots        # For plotting, alternative to matplotlib.pyplot
using DSP          # For signal processing, has many functionalities similar to scipy.signal
# using Librosa    # Placeholder, as of 2021 there isn't a direct Julia equivalent to librosa
using FileIO       # For general file operations
# using Keyboard   # If there's a need for keyboard-related operations in Julia
using PyCall       # For calling Python libraries from Julia if required
using Pkg          # For package-related operations

# For setting environment variables
ENV["NUMBA_NUM_THREADS"] = "1"

#=
Notes:

Some of the Python libraries may not have direct Julia counterparts. In such cases, you might either find an alternative library in Julia or use PyCall to call the Python library directly from Julia.
The provided translations are based on the closest functionality available in Julia. Depending on your needs, you might need to adjust, add, or remove some packages.
Before using a Julia package, you need to install it using Pkg.add("PackageName").
This list doesn't cover all the functionalities of the provided Python libraries. Depending on the specific functions you need, further modifications or additions might be required.
=#

using Dates, Base.Threads, Base.Signals

# Initialize the lock
lock = ReentrantLock()

# In Julia, ignoring warnings would typically involve the `@suppress` macro from the `Suppressor.jl` package.
# For the sake of this translation, I'll just include a placeholder comment.
# You might want to add `using Suppressor` and wrap the code you want to suppress warnings for with `@suppress`.

# Signal handling
function signal_handler(sig)
    println("Stopping all threads...")
    stop_all()   # Assuming the existence of this function in the rest of your code
    exit(0)
end

# Attach the signal handler
signals = [SIGINT, SIGTERM]
for sig in signals
    siginterrupt(sig, false)
    signal(sig, signal_handler)
end

# Initialize recording variables
continuous_start_index = nothing
continuous_end_index = 0
period_start_index = nothing
event_start_index = nothing
detected_level = nothing

# threads
recording_worker_thread = nothing

# Processes
vu_proc = nothing
stop_vu_queue = nothing
oscope_proc = nothing
intercom_proc = nothing
fft_periodic_plot_proc = nothing
one_shot_fft_proc = nothing

# Event flags
stop_recording_event = Threads.Event()
stop_tod_event = Threads.Event()
stop_vu_event = Threads.Event()
stop_intercom_event = Threads.Event()
stop_fft_periodic_plot_event = Threads.Event()

trigger_oscope_event = Threads.Event()
trigger_fft_event = Threads.Event()
stop_worker_event = Threads.Event()

# Queues
stop_vu_queue = nothing

# Misc globals
_dtype = nothing  # Parameters the sd lib cares about
_subtype = nothing
asterisks = '*'
device_ch = nothing
current_time = nothing
timestamp = nothing
monitor_channel = 0
stop_program = [false]
buffer_size = nothing
buffer = nothing
buffer_index = nothing


# Control Panel variables


# Mode controls
MODE_AUDIO_MONITOR = true
MODE_PERIOD = true
MODE_EVENT = false
MODE_FFT_PERIODIC_RECORD = true

KB_or_CP = "KB"

# Audio hardware config
device_id = 0

if device_id == 0
    SOUND_IN = 1
    SOUND_OUT = 3
    SOUND_CHS = 2
elseif device_id == 1
    SOUND_IN = 17
    SOUND_OUT = 14
    SOUND_CHS = 2
elseif device_id == 2
    SOUND_IN = 16
    SOUND_OUT = 14
    SOUND_CHS = 2
elseif device_id == 3
    SOUND_IN = 16
    SOUND_OUT = 14
    SOUND_CHS = 4
else
    SOUND_IN = 1
    SOUND_OUT = 3
    SOUND_CHS = 2
end

# Audio parameters
PRIMARY_SAMPLE_RATE = 192000
PRIMARY_BIT_DEPTH = 16
PRIMARY_FILE_FORMAT = "FLAC"
AUDIO_MONITOR_SAMPLE_RATE = 48000
AUDIO_MONITOR_BIT_DEPTH = 16
AUDIO_MONITOR_CHANNELS = 2
AUDIO_MONITOR_QUALITY = 0
AUDIO_MONITOR_FORMAT = "MP3"

# Recording types controls
AUDIO_MONITOR_START = Time(4, 0, 0)
AUDIO_MONITOR_END = Time(23, 0, 0)
AUDIO_MONITOR_RECORD = 1800
AUDIO_MONITOR_INTERVAL = 0

PERIOD_START = Time(4, 0, 0)
PERIOD_END = Time(20, 0, 0)
PERIOD_RECORD = 300
PERIOD_INTERVAL = 0

EVENT_START = Time(4, 0, 0)
EVENT_END = Time(22, 0, 0)
SAVE_BEFORE_EVENT = 30
SAVE_AFTER_EVENT = 30
EVENT_THRESHOLD = 20000
MONITOR_CH = 0
TRACE_DURATION = 10
OSCOPE_GAIN_DB = 10

# Instrumentation parameters
FFT_BINS = 900
FFT_BW = 1000
FFT_DURATION = 5
FFT_GAIN = 20
FFT_INTERVAL = 30

OSCOPE_DURATION = 10
OSCOPE_GAIN = 20

FULL_SCALE = 2 ^ 16
BUFFER_SECONDS = 1000

# Translate human to machine
if PRIMARY_BIT_DEPTH == 16
    _dtype = "int16"
    _subtype = "PCM_16"
elseif PRIMARY_BIT_DEPTH == 24
    _dtype = "int24"
    _subtype = "PCM_24"
elseif PRIMARY_BIT_DEPTH == 32
    _dtype = "int32"
    _subtype = "PCM_32"
else
    println("The bit depth is not supported: ", PRIMARY_BIT_DEPTH)
    exit(-1)
end

SIGNAL_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"
PLOT_DIRECTORY = "D:/OneDrive/data/Zeev/plots"

# Location and hive ID
LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1"

#=
Notes:
1. Julia uses `nothing` instead of Python's `None`.
2. Julia uses `true` and `false` for boolean values.
3. Julia's `if-elseif-else-end` replaces Python's `if-elif-else`.
4. Julia uses `^` for exponentiation instead of Python's `**`.
5. In Julia, `Time` from the `Dates` module is equivalent to Python's `datetime.time`.
6. In Julia, the `exit()` function is used to terminate a program, similar to Python's `sys.exit()`.
7. The translated code assumes that any functions referred to in the Python code (like `stop_all()`) will be defined or translated elsewhere in your Julia code.
=#

using SoundFile, SoundDevice, PyCall

######################
# Misc utilities
######################

# Interruptable sleep
function sleep(seconds, stop_sleep_event)
    for _ in 1:seconds
        if is_set(stop_sleep_event)
            return
        end
        sleep(1)
    end
end

# For debugging
function play_audio(filename, device)
    println("* Playing back")
    data, fs = SoundFile.read(filename)
    SoundDevice.play(data, fs, device)
    SoundDevice.wait()
end

function show_audio_device_info_for_SOUND_IN_OUT()
    device_info = SoundDevice.query_devices(SOUND_IN)
    println("Default Sample Rate: ", device_info["default_samplerate"])
    println("Max Input Channels: ", device_info["max_input_channels"])
    device_info = SoundDevice.query_devices(SOUND_OUT)
    println("Default Sample Rate: ", device_info["default_samplerate"])
    println("Max Output Channels: ", device_info["max_output_channels"])
    println()
    println()
end

function show_audio_device_info_for_defaults()
    println("\nSoundDevice default device info:")
    default_input_info = SoundDevice.query_devices(kind="input")
    default_output_info = SoundDevice.query_devices(kind="output")
    println("\nDefault Input Device: ", default_input_info)
    println("Default Output Device: ", default_output_info, "\n")
end

function show_audio_device_list()
    println(SoundDevice.query_devices())
    show_audio_device_info_for_defaults()
    println("\nCurrent device in: ", SOUND_IN, ", device out: ", SOUND_OUT, "\n")
    show_audio_device_info_for_SOUND_IN_OUT()
end

function find_file_of_type_with_offset(directory=SIGNAL_DIRECTORY, file_type=PRIMARY_FILE_FORMAT, offset=0)
    matching_files = [file for file in readdir(directory) if endswith(file, ".$file_type")]
    
    if offset < length(matching_files)
        println("Spectrogram found: ", matching_files[offset])
        return matching_files[offset]
    end

    return nothing
end

##########################
# Audio conversion functions
##########################

function pcm_to_mp3_write(np_array, full_path)
    int_array = Int16.(np_array)
    byte_array = Int16.(int_array)

    # Create an AudioSegment instance from the byte array using PyDub
    py_audio_segment = pyimport("pydub.AudioSegment")
    audio_segment = py_audio_segment(data=byte_array, sample_width=2, frame_rate=AUDIO_MONITOR_SAMPLE_RATE, channels=AUDIO_MONITOR_CHANNELS)
    if AUDIO_MONITOR_QUALITY >= 64 && AUDIO_MONITOR_QUALITY <= 320
        cbr = string(AUDIO_MONITOR_QUALITY) * "k"
        audio_segment.export(full_path, format="mp3", bitrate=cbr)
    elseif AUDIO_MONITOR_QUALITY < 10
        audio_segment.export(full_path, format="mp3", parameters=["-q:a", "0"])
    else
        println("Don't know of an mp3 mode with parameter: ", AUDIO_MONITOR_QUALITY)
        exit(-1)
    end
end

function downsample_audio(audio_data, orig_sample_rate, target_sample_rate)
    audio_float = audio_data ./ Float32(typemax(Int16))
    downsample_ratio = div(orig_sample_rate, target_sample_rate)
    
    # Use DSP.jl for filtering and down-sampling
    nyq = 0.5 * orig_sample_rate
    low = 0.5 * target_sample_rate
    low /= nyq
    b, a = DSP.butter(5, low, btype="low")

    if size(audio_float, 2) == 2
        left_channel = audio_float[:, 1]
        right_channel = audio_float[:, 2]
    else
        left_channel = vec(audio_float)
        right_channel = vec(audio_float)
    end

    left_filtered = DSP.filtfilt(b, a, left_channel)
    right_filtered = DSP.filtfilt(b, a, right_channel)
    left_downsampled = left_filtered[1:downsample_ratio:end]
    right_downsampled = right_filtered[1:downsample_ratio:end]
    downsampled_audio_float = hcat(left_downsampled, right_downsampled)
    downsampled_audio = Int16.(downsampled_audio_float .* typemax(Int16))
    return downsampled_audio
end

#=
Notes:

Julia's SoundFile and SoundDevice are placeholders for the equivalent packages you might use for audio reading, writing, and playback. If exact equivalents don't exist, you might need to use PyCall to directly call Python libraries, or find Julia libraries that offer similar functionality.
The audio conversion functions use PyDub in Python. In the translation, I've used PyCall to directly call this Python library from Julia.
Julia's DSP package is assumed to be an equivalent to parts of scipy.signal for filtering purposes.
Julia uses . for broadcasting, which allows element-wise operations on arrays.
This translation assumes that the functions and constants referred to (like is_set) will be defined or translated elsewhere in your Julia code.
=#

using SoundDevice, PyPlot, FFTW, Librosa, Dates, Base.Threads

##########################
# Signal display functions
##########################

# Single-shot plot of 'n' seconds of audio of each channels for an oscope view
function plot_oscope()
    global monitor_channel

    # Convert gain from dB to linear scale
    gain = 10^(OSCOPE_GAIN_DB / 20)
    
    # Record audio
    println("Recording audio for oscope traces for ch count: ", SOUND_CHS)
    o_recording = SoundDevice.rec(Int(PRIMARY_SAMPLE_RATE * TRACE_DURATION), samplerate=PRIMARY_SAMPLE_RATE, channels=SOUND_CHS)
    SoundDevice.wait()  # Wait until recording is finished
    println("Recording oscope finished.")

    o_recording .*= gain

    figure()
    # Plot number of channels
    for i in 1:SOUND_CHS
        subplot(2, 1, i)
        plot(o_recording[:, i])
        title("Channel $i")
        ylim(-0.5, 0.5)
    end

    tight_layout()
    show()
end

# Single-shot fft plot of audio
function plot_fft()
    global monitor_channel

    N = PRIMARY_SAMPLE_RATE * FFT_DURATION  # Number of samples
    
    # Convert gain from dB to linear scale
    gain = 10^(FFT_GAIN / 20)
    
    # Record audio
    println("Recording audio for fft one shot...")
    myrecording = SoundDevice.rec(Int(N), samplerate=PRIMARY_SAMPLE_RATE, channels=monitor_channel + 1)
    SoundDevice.wait()  # Wait until recording is finished
    myrecording .*= gain
    println("Recording fft finished.")
    
    # Perform FFT
    yf = rfft(vec(myrecording))
    xf = rfftfreq(N, 1 / PRIMARY_SAMPLE_RATE)

    # Define bucket width
    bucket_width = FFT_BW  # Hz
    bucket_size = Int(bucket_width * N / PRIMARY_SAMPLE_RATE)  # Number of indices per bucket

    # Average buckets
    buckets = [mean(yf[i:i + bucket_size]) for i in 1:bucket_size:length(yf)]
    bucket_freqs = [mean(xf[i:i + bucket_size]) for i in 1:bucket_size:length(xf)]

    # Plot results
    plot(bucket_freqs, abs.(buckets))
    xlabel("Frequency (Hz)")
    ylabel("Amplitude")
    title("FFT Plot monitoring ch: $(monitor_channel + 1) of $SOUND_CHS channels")
    grid(true)
    show()
end

# One-shot spectrogram plot of audio in a separate process
function plot_spectrogram(audio_path=spectrogram_audio_path, output_image_path=output_image_path, y_axis_type="lin", y_decimal_places=2)
    if find_file_of_type_with_offset() === nothing
        println("No data available to see?")
        return
    else
        audio_path = joinpath(SIGNAL_DIRECTORY, find_file_of_type_with_offset())  # Quick hack to eval code
    end

    # Load the audio file (only up to 300 seconds or the end of the file, whichever is shorter)
    y, sr = Librosa.load(audio_path, sr=nothing, duration=PERIOD_RECORD)
    
    # Compute the spectrogram
    D = Librosa.amplitude_to_db(abs.(Librosa.stft(y)), ref=maximum(y))
    
    # Plot the spectrogram
    figure(figsize=(10, 4))
    
    if y_axis_type == "log"
        Librosa.display.specshow(D, sr=sr, x_axis="time", y_axis="log")
    elseif y_axis_type == "lin"
        Librosa.display.specshow(D, sr=sr, x_axis="time", y_axis="linear")
    else
        error("y_axis_type must be 'log' or 'linear'")
    end

    # Adjust y-ticks to be in kilohertz and have the specified number of decimal places
    y_ticks = gca().get_yticks()
    gca().set_yticklabels(["$(round(tick/1000, digits=y_decimal_places)) kHz" for tick in y_ticks])
    
    colorbar(format="%+2.0f dB")
    title("Spectrogram")
    tight_layout()
    # savefig(output_image_path, dpi=300)
    show()
end

# Continuous fft plot of audio in a separate background process
function plot_and_save_fft()
    global monitor_channel, stop_fft_periodic_plot_event, fft_periodic_plot_proc

    interval = FFT_INTERVAL * 60    # Convert to seconds, time between ffts
    N = PRIMARY_SAMPLE_RATE * FFT_DURATION  # Number of samples
    
    # Convert gain from dB to linear scale
    gain = 10^(FFT_GAIN / 20)

    while !is_set(stop_fft_periodic_plot_event)
        # Record audio
        println("Recording audio for auto fft in $FFT_INTERVAL minutes...")
        # Wait for the desired time interval before recording and plotting again
        sleep(interval, stop_fft_periodic_plot_event)
            
        myrecording = SoundDevice.rec(Int(N), samplerate=PRIMARY_SAMPLE_RATE, channels=monitor_channel + 1)
        SoundDevice.wait()  # Wait until recording is finished
        myrecording .*= gain
        println("Recording auto fft finished.")

        # Perform FFT
        yf = rfft(vec(myrecording))
        xf = rfftfreq(N, 1 / PRIMARY_SAMPLE_RATE)




   
        using PyCall, SharedArrays, Distributed
        
        # Reference necessary Python libraries
        np = pyimport("numpy")
        sd = pyimport("sounddevice")
        
        ##########################
        # VU Meter functions
        ##########################
        
        function vu_meter(stop_vu_queue, asterisks)
            global monitor_channel, device_ch
        
            buffer = SharedArray{Float64}(PRIMARY_SAMPLE_RATE,)
        
            function callback_input(indata, frames, time, status)
                global monitor_channel
                # Only process audio from the designated channel
                channel_data = indata[:, monitor_channel+1]
                buffer[1:frames] = channel_data
        
                audio_level = np.max(np.abs(channel_data))
                normalized_value = Int((audio_level / 1.0) * 50)  
        
                asterisks.value = '*' ^ normalized_value
                println(asterisks.value * " " ^ (50 - normalized_value) * "\r", end="")
            end
        
            stream = sd.InputStream(callback=callback_input, channels=SOUND_CHS, samplerate=PRIMARY_SAMPLE_RATE)
            stream.start()
            while !take!(stop_vu_queue)
                sleep(0.1)
            end
            println("Stopping vu...")
            stream.stop()
        end
        
        function stop_vu()
            global vu_proc, stop_vu_event, stop_vu_queue
        
            if vu_proc !== nothing
                put!(stop_vu_queue, true)
                wait(vu_proc)
                vu_proc = nothing
                println("\nvu stopped")
            end
        end
        
        function toggle_vu_meter()
            global vu_proc, monitor_channel, asterisks, stop_vu_queue
        
            if vu_proc === nothing
                println("\nVU meter monitoring channel: ", monitor_channel)
                stop_vu_queue = Channel(1)
                asterisks = "*" ^ 50
                println("fullscale: ", asterisks)
        
                if MODE_EVENT
                    normalized_value = Int(EVENT_THRESHOLD / 1000)
                    asterisks = "*" ^ normalized_value
                    println("threshold: ", asterisks)
                end
        
                vu_proc = @async vu_meter(stop_vu_queue, asterisks)
            else
                stop_vu()
            end
        end
        
        ##########################
        # Intercom functions
        ##########################
        
        function intercom()
            global monitor_channel
        
            buffer = SharedArray{Float64}(PRIMARY_SAMPLE_RATE,)
            channel = monitor_channel
        
            function callback_input(indata, frames, time, status)
                channel_data = indata[:, channel+1]
                buffer[1:frames] = channel_data
            end
        
            function callback_output(outdata, frames, time, status)
                outdata[:, 1] = buffer[1:frames]
                outdata[:, 2] = buffer[1:frames]
            end
        
            input_stream = sd.InputStream(callback=callback_input, device=SOUND_IN, channels=SOUND_CHS, samplerate=PRIMARY_SAMPLE_RATE)
            output_stream = sd.OutputStream(callback=callback_output, device=3, channels=2, samplerate=44100)
        
            input_stream.start()
            output_stream.start()
            while !is_set(stop_intercom_event)
                sleep(1)
            end
            println("Stopping intercom...")
            input_stream.stop()
            output_stream.stop()
        end
        
        function stop_intercom()
            global intercom_proc
        
            if intercom_proc !== nothing
                stop_intercom_event[] = true
                wait(intercom_proc)
                println("\nIntercom stopped")
                intercom_proc = nothing
            end
        end
        
        function toggle_intercom()
            global intercom_proc
        
            if intercom_proc === nothing
                println("Starting intercom...")
                println("listening to channel 0", end="\r")
                intercom_proc = @async intercom()
            else
                stop_intercom()
            end
        end

        #=
        Some notes on the translation:
        - Julia's 1-indexed arrays were considered, so we add 1 when referencing the monitor channel.
        - Used `SharedArray` in place of Python's multiprocessing shared memory.
        - Replaced Python's `multiprocessing` with Julia's native `@async` and `Channel` for asynchronous tasks and communication.
        - Used a single channel instead of a queue for signaling the stopping of the VU meter.
        - The `is_set` function checks if a value exists in a shared array or dictionary, but it's not provided here. You might want to implement it based on your application's needs.
        
        This is a direct translation, and the functionality should be the same, but you may need to adjust depending on your specific Julia environment or other code dependencies.
        =#

using PyCall, SharedArrays, Distributed, Threads, Dates, DSP, SoundFile

# Reference necessary Python libraries
np = pyimport("numpy")
sd = pyimport("sounddevice")

##########################
# Audio stream & callback functions
##########################

# Audio buffers and variables
buffer_size = Int(BUFFER_SECONDS * PRIMARY_SAMPLE_RATE)
buffer = SharedArray{Float64}(buffer_size, SOUND_CHS)
buffer_index = 1
blocksize = 8196
buffer_wrap_event = Threads.Event()

# Global variables (these need to be defined elsewhere in your code)
# _dtype, BUFFER_SECONDS, PRIMARY_SAMPLE_RATE, SOUND_CHS, MODE_AUDIO_MONITOR, AUDIO_MONITOR_RECORD, AUDIO_MONITOR_INTERVAL, 
# AUDIO_MONITOR_FORMAT, AUDIO_MONITOR_SAMPLE_RATE, AUDIO_MONITOR_START, AUDIO_MONITOR_END, MODE_PERIOD, PERIOD_RECORD, 
# PERIOD_INTERVAL, PRIMARY_FILE_FORMAT, PERIOD_START, PERIOD_END, MODE_EVENT, SAVE_BEFORE_EVENT, SAVE_AFTER_EVENT, 
# EVENT_START, EVENT_END, stop_program


using Dates, SoundFile

function recording_worker_thread(record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod)
    # Global variables used in the function. Ensure their definitions and initializations elsewhere.
    global buffer, buffer_size, buffer_index, stop_recording_event, PRIMARY_SAMPLE_RATE, SIGNAL_DIRECTORY, LOCATION_ID, HIVE_ID

    if start_tod === nothing
        println("$(thread_id) is recording continuously")
    end

    samplerate = PRIMARY_SAMPLE_RATE

    while !is_set(stop_recording_event)  # You'll need to define the `is_set` function or use appropriate Julia synchronization primitives.

        current_time = Dates.Time(Dates.now())

        if start_tod === nothing || (start_tod <= current_time <= end_tod)
            println("$(thread_id) recording started at: $(Dates.now()) for $(record_period) sec, interval $(interval) sec")

            period_start_index = buffer_index

            # Assuming you have a sleep function that takes into account the `stop_recording_event`
            sleep(record_period)

            period_end_index = buffer_index

            save_start_index = mod(period_start_index, buffer_size)
            save_end_index = mod(period_end_index, buffer_size)

            # Saving from a circular buffer so segments aren't necessarily contiguous
            if save_end_index > save_start_index
                audio_data = buffer[save_start_index:save_end_index]
            else
                audio_data = vcat(buffer[save_start_index:end], buffer[1:save_end_index])
            end

            if target_sample_rate < PRIMARY_SAMPLE_RATE
                # Resample to a lower sample rate
                audio_data = downsample_audio(audio_data, PRIMARY_SAMPLE_RATE, target_sample_rate)  # Ensure this function is defined in Julia
            end

            timestamp = Dates.format(Dates.now(), "yyyymmdd-HHMMSS")
            output_filename = "$(timestamp)_$(thread_id)_$(record_period)_$(interval)_$(LOCATION_ID)_$(HIVE_ID).$(lowercase(file_format))"

            full_path_name = joinpath(SIGNAL_DIRECTORY, output_filename)

            if uppercase(file_format) == "MP3"
                if target_sample_rate in [44100, 48000]
                    pcm_to_mp3_write(audio_data, full_path_name)  # Ensure this function is defined in Julia
                else
                    println("mp3 only supports 44.1k and 48k sample rates")
                    exit(-1)
                end
            else
                SoundFile.write(full_path_name, audio_data, target_sample_rate; format=uppercase(file_format))
            end

            if !is_set(stop_recording_event)
                println("Saved $(thread_id) audio to $(full_path_name), period: $(record_period), interval $(interval) seconds")
            end

            # Wait "interval" seconds before starting recording again
            sleep(interval)
        end
    end
end

#=
Notes:

Julia's built-in Dates module is used instead of Python's datetime.
Julia uses nothing instead of Python's None.
Julia doesn't support in-place string formatting like Python's f-strings. Instead, string interpolation using $ inside strings is used.
Julia doesn't have a direct counterpart to Python's global keyword. In Julia, if you modify a global variable inside a function, you need to declare it with global inside that function.
Function calls and other logic are translated directly, but you may need to ensure that functions like downsample_audio and pcm_to_mp3_write are defined in Julia, as they're external to the provided code.
The sleep function in Julia doesn't take a stop_recording_event. If you have a custom sleep function that takes this into account, you'll need to ensure its definition in Julia. Otherwise, you might need to adapt the logic or use Julia synchronization primitives.
This translation should provide a good starting point, but you might need to make additional adjustments and optimizations based on the broader context of your Julia application.
=#


function callback(indata, frames, time, status)
    # Global variables used in the function. Ensure their definitions and initializations elsewhere.
    global buffer, buffer_index, buffer_size, buffer_wrap_event

    # Note: In Julia, you don't need to specify "global" inside a function unless you're modifying the global variable.

    if status != nothing
        println("Callback status: ", status)
    end

    data_len = length(indata)

    # Managing the circular buffer
    if buffer_index + data_len <= buffer_size
        buffer[buffer_index+1:buffer_index + data_len] = indata
        # Assuming buffer_wrap_event is a condition variable or another synchronization primitive in Julia
        notify(buffer_wrap_event)  # Equivalent of `clear` in Python
    else
        overflow = buffer_index + data_len - buffer_size
        buffer[buffer_index+1:end] = indata[1:end-overflow]
        buffer[1:overflow] = indata[end-overflow+1:end]
        # Assuming buffer_wrap_event is a condition variable or another synchronization primitive in Julia
        wait(buffer_wrap_event)   # Equivalent of `set` in Python
    end

    buffer_index = mod(buffer_index + data_len, buffer_size)
end


#=
Notes:

Julia uses 1-based indexing, so we've adjusted the index calculations in the array slicing operations.
We assume that buffer_wrap_event corresponds to some kind of synchronization primitive in Julia, perhaps a Condition variable. Depending on its exact nature in your Julia code, you might need to adjust the way you signal or wait on this event.
The logic and structure of the function remain largely the same, with adjustments for Julia's syntax and conventions.
=#

#=
In Julia, you'd typically utilize the Threads module for multithreading. Also, note that the sound processing libraries in Python and Julia might have different interfaces, so the actual API calls might need adjustment. Here's a translation that stays as close to the Python logic as possible:
=#

using Threads

function audio_stream()
    global stop_program

    println("Start audio_stream...")

    # Assuming there's a similar library for audio streaming in Julia
    # The API call might differ; this is a placeholder
    stream = InputStream(device=SOUND_IN, channels=SOUND_CHS, samplerate=PRIMARY_SAMPLE_RATE, dtype=_dtype, blocksize=blocksize, callback=callback)

    try
        # Start the recording worker threads
        # These threads will run until the program is stopped. They will not stop when the stream is stopped.
        # Replace <name>_START with nothing (equivalent to Python's None) to disable time of day recording.
        
        if MODE_AUDIO_MONITOR
            println("Starting recording_worker_thread for down sampling audio to 48k and saving mp3...")
            Threads.@spawn recording_worker_thread(AUDIO_MONITOR_RECORD, AUDIO_MONITOR_INTERVAL, "Audio_monitor", AUDIO_MONITOR_FORMAT, AUDIO_MONITOR_SAMPLE_RATE, AUDIO_MONITOR_START, AUDIO_MONITOR_END)
        end
        
        if MODE_PERIOD
            println("Starting recording_worker_thread for saving period audio at primary sample rate and all channels...")
            Threads.@spawn recording_worker_thread(PERIOD_RECORD, PERIOD_INTERVAL, "Period_recording", PRIMARY_FILE_FORMAT, PRIMARY_SAMPLE_RATE, PERIOD_START, PERIOD_END)
        end

        if MODE_EVENT  # *** UNDER CONSTRUCTION, NOT READY FOR PRIME TIME ***
            println("Starting recording_worker_thread for saving event audio at primary sample rate and trigger by event...")
            Threads.@spawn recording_worker_thread(SAVE_BEFORE_EVENT, SAVE_AFTER_EVENT, "Event_recording", PRIMARY_FILE_FORMAT, PRIMARY_SAMPLE_RATE, EVENT_START, EVENT_END)
        end

        while stream.active && !stop_program[1]
            sleep(1.0)
        end

        # Assuming there's a method to stop the stream in Julia's equivalent audio library
        stop(stream)
        
    finally
        println("Stopped audio_stream...")
    end
end

#=
Please note:

The try ... finally block in Julia serves the same purpose as the with statement in Python, ensuring that resources are cleaned up.
I've used Threads.@spawn for threading in Julia. The multithreading in Julia might differ from Python's threading, so you might need to adjust accordingly.
The structure and logic remain the same. Adjustments have been made for Julia's syntax and conventions.
You'll need to replace the placeholder functions and methods with actual Julia methods from the appropriate libraries.
=#


using Printf
using Dates

# Define the main function
function main()
    global time_of_day_thread, fft_periodic_plot_proc, oscope_proc, one_shot_fft_proc, monitor_channel

    println("Acoustic Signal Capture\n")
    @printf("buffer size: %d second, %.2f megabytes\n", BUFFER_SECONDS, sizeof(buffer) / 1000000)
    @printf("Sample Rate: %d; File Format: %s; Channels: %d\n", PRIMARY_SAMPLE_RATE, PRIMARY_FILE_FORMAT, SOUND_CHS)
    
    # Check on input device parms or if input device even exits
    try
        println("These are the available devices: \n")
        show_audio_device_list()
        device_info = query_devices(SOUND_IN)
        device_ch = device_info["max_input_channels"]
        
        if SOUND_CHS > device_ch
            @printf("The device only has %d channel(s) but requires %d channels.\n", device_ch, SOUND_CHS)
            println("These are the available devices: \n", query_devices())
            exit(-1)
        end
    catch e
        println("An error occurred while attempting to access the input device: ", e)
        exit(-1)
    end

    # Create the output directory if it doesn't exist
    try
        mkpath(SIGNAL_DIRECTORY)
        mkpath(PLOT_DIRECTORY)
    catch e
        println("An error occurred while trying to make or find output directory: ", e)
        exit(-1)
    end

    # The rest of your functions like trigger_oscope(), trigger_fft(), and so on should be translated similarly. 

    # You'd then handle the keyboard input. In Julia, this might be done differently. For simplicity, I'll provide a simple REPL loop:

    println("Enter command (q to quit): ")
    command = readline()
    while command != "q"
        # Handle commands like "f", "o", and so on. 
        # Note: You'd likely want a more sophisticated event-driven approach for a production system.
        
        if command == "f"
            trigger_fft()
        elseif command == "o"
            trigger_oscope()
        # ... handle other commands ...

        println("Enter command (q to quit): ")
        command = readline()
    end

    # Ensure all tasks are stopped properly.
    stop_all()

    println("\nHopefully we have turned off all the lights...")
end

# Run the main function when this script is executed.
main()


#=
Please note:

Julia doesn't have an equivalent to Python's if __name__ == "__main__":, so you just call the main() function at the end of the script.
Error handling in Julia uses try ... catch rather than try ... except.
You'd need to find or create Julia equivalents for all the Python-specific functions and libraries.
The way user input is handled in this translation is rudimentary and uses a simple REPL loop. You might want to use a more sophisticated approach in a production system.
=#

#=
Some notes on the translation:

I've translated the structure of the functions and added placeholders for the function bodies. You'll need to adapt the function bodies to fit Julia's syntax and libraries.
The Threads.Event() in Julia is used to synchronize tasks within threads similarly to Python's threading Event.
Julia's arrays are 1-indexed. This means that where you start at 0 in Python, you'll start at 1 in Julia.
For the sake of brevity and clarity, I've not translated the entire function body but provided an outline. The core logic within each function needs to be translated and adapted to Julia's syntax and available libraries.
Global variables used in the functions are noted, and you need to ensure their definitions and initializations in the broader context of your Julia program.
The direct functionality conversion from Python to Julia can be intricate, especially when dealing with threading and real-time audio processing. Depending on the specific requirements and dependencies in your application, additional adjustments and optimizations may be necessary.
=#

