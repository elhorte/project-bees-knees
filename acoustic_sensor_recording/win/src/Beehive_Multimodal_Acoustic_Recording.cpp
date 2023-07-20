#!/usr/bin/env c++

#include <iostream>
#include <thread>
#include <chrono>
#include <mutex>
#include <deque>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <portaudio.h>
#include <sndfile.h>

// Threshold, sample rate, etc. 
// These can be adjusted as necessary.
const int THRESHOLD = 27000;
const int SAMPLE_RATE = 192000;
const int BUFFER_SECONDS = 400;
const int CHANNELS = 2;
const int PERIOD = 60;
const int INTERVAL = 300;
const int SAVE_BEFORE_EVENT = 30;
const int SAVE_AFTER_EVENT = 30;
const std::string OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings";
const std::string FORMAT = "FLAC";

// Global data for the recording.
std::deque<float> buffer;
std::mutex bufferMutex;
std::atomic<int> bufferIndex(0);

// The recording callback
int recordCallback(const void* input, void* output, unsigned long frameCount, 
    const PaStreamCallbackTimeInfo* timeInfo, 
    PaStreamCallbackFlags statusFlags, void* userData) {
    float* in = (float*)input;

    std::lock_guard<std::mutex> lock(bufferMutex);

    for (int i = 0; i < frameCount; i++) {
        buffer.push_back(*in++);
        if (buffer.size() > SAMPLE_RATE * BUFFER_SECONDS) {
            buffer.pop_front();
        }
    }

    bufferIndex += frameCount;
    if (bufferIndex >= SAMPLE_RATE * BUFFER_SECONDS) {
        bufferIndex -= SAMPLE_RATE * BUFFER_SECONDS;
    }

    return paContinue;
}

void writeWavFile(std::string filename, float* data, int size) {
    SF_INFO sfinfo;
    sfinfo.channels = 1;
    sfinfo.samplerate = SAMPLE_RATE;
    sfinfo.format = SF_FORMAT_WAV | SF_FORMAT_PCM_16;
    SNDFILE* outfile = sf_open(filename.c_str(), SFM_WRITE, &sfinfo);
    if (!outfile) {
        std::cerr << "Failed to open file: " << filename << "\n";
        return;
    }

    sf_write_float(outfile, data, size);
    sf_close(outfile);
}

void checkLevelThreadFunc() {
    float* data = new float[SAMPLE_RATE * (SAVE_BEFORE_EVENT + SAVE_AFTER_EVENT)];

    while (true) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));

        std::lock_guard<std::mutex> lock(bufferMutex);
        float level = *std::max_element(buffer.begin(), buffer.end());
        if (level > THRESHOLD) {
            std::copy(buffer.begin() + bufferIndex, buffer.end(), data);
            std::copy(buffer.begin(), buffer.begin() + bufferIndex, data + (buffer.size() - bufferIndex));

            // Write the file in a separate thread so it doesn't block the level check
            std::thread([data] {
                std::string filename = OUTPUT_DIRECTORY + "/event.wav";
                writeWavFile(filename, data, SAMPLE_RATE * (SAVE_BEFORE_EVENT + SAVE_AFTER_EVENT));
                delete[] data;
            }).detach();

            // Allocate a new buffer
            data = new float[SAMPLE_RATE * (SAVE_BEFORE_EVENT + SAVE_AFTER_EVENT)];
        }
    }
}

int main(void) {
    // Initialize PortAudio
    Pa_Initialize();

    // Set up the input parameters
    PaStreamParameters inputParameters;
    inputParameters.device = Pa_GetDefaultInputDevice();
    inputParameters.channelCount = CHANNELS;
    inputParameters.sampleFormat = paFloat32;
    inputParameters.suggestedLatency = Pa_GetDeviceInfo(inputParameters.device)->defaultLowInputLatency;
    inputParameters.hostApiSpecificStreamInfo = NULL;

    // Start the stream
    PaStream* stream;
    Pa_OpenStream(&stream, &inputParameters, NULL, SAMPLE_RATE, paFramesPerBufferUnspecified, paNoFlag, recordCallback, NULL);
    Pa_StartStream(stream);

    // Start the level check thread
    std::thread checkLevelThread(checkLevelThreadFunc);

    // Wait for the threads to finish
    checkLevelThread.join();
    Pa_StopStream(stream);

    // Clean up PortAudio
    Pa_Terminate();

    return 0;
}


// ------------------------------------------------------------------------------    
// Alternative: use the PortAudio library to record audio using a circular buffer
// ------------------------------------------------------------------------------

/* 
Ct6ircular buffer in C++ for the audio stream. In the code below, I am using `deque` data structure to implement the circular buffer.

We will be maintaining a buffer of size equal to `SAMPLE_RATE * PERIOD`, and with each new input frame, we will add it to the back of our buffer and remove elements from the front to maintain the size. When we need to write to a file, we can simply take all the elements from the buffer.
*/

#include <deque>
#include <vector>
#include <chrono>
#include <thread>
#include <fstream>
#include <iostream>
#include <cstring>
#include <cstdlib>
#include <RtAudio.h>

#define SAMPLE_RATE 44100
#define CHANNELS 2
#define BUFFER_SECONDS 5
#define INTERVAL 10
#define PERIOD 5

std::deque<int16_t> audioBuffer;
unsigned int bufferMaxSize = SAMPLE_RATE * CHANNELS * PERIOD;

int audioCallback(void *outputBuffer, void *inputBuffer, unsigned int nBufferFrames,
                  double streamTime, RtAudioStreamStatus status, void *userData) {
    unsigned int size = nBufferFrames * CHANNELS;
    int16_t* ptr = reinterpret_cast<int16_t*>(inputBuffer);

    for (unsigned int i = 0; i < size; ++i) {
        audioBuffer.push_back(ptr[i]);
        if (audioBuffer.size() > bufferMaxSize)
            audioBuffer.pop_front();
    }

    return 0;
}

void saveAudio() {
    std::ofstream outFile("output.pcm", std::ios::binary);
    for (auto& sample : audioBuffer) {
        outFile.write(reinterpret_cast<char*>(&sample), sizeof(int16_t));
    }
    outFile.close();
}

void audioStream(RtAudio& audio) {
    RtAudio::StreamParameters parameters;
    parameters.deviceId = audio.getDefaultInputDevice();
    parameters.nChannels = CHANNELS;
    parameters.firstChannel = 0;

    unsigned int bufferFrames = 256;

    try {
        audio.openStream(NULL, &parameters, RTAUDIO_SINT16, SAMPLE_RATE, &bufferFrames, &audioCallback);
        audio.startStream();

        while (true) { 
            std::this_thread::sleep_for(std::chrono::seconds(PERIOD));

            saveAudio();
            
            std::this_thread::sleep_for(std::chrono::seconds(INTERVAL - PERIOD));
        }
    }
    catch (RtAudioError& e) {
        e.printMessage();
    }
}

int main() {
    RtAudio audio;
    audioStream(audio);
    return 0;
}

/*

Note: This is a simplified version of what you may need, and it doesn't handle errors or edge cases. The output file is overwritten every time and it doesn't handle the case when the device can't provide enough frames or the case when the device is disconnected. It also doesn't stop the recording on keyboard interruption like Ctrl+C.

*/
