#!/usr/bin/env c++

#include <RtAudio.h>
#include <sndfile.h>
#include <iostream>
#include <stdexcept>
#include <cmath>
#include <chrono>
#include <ctime>
#include <thread>
#include <vector>
#include <algorithm>
#include <mutex>

const int SAMPLE_RATE = 192000;
const int CHANNELS = 2;
const int BIT_DEPTH = 16;
const int BUFFER_SIZE = 400 * SAMPLE_RATE;
const std::string FORMAT = "FLAC";
const std::string OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings";
const int INTERVAL = 300;

std::vector<int16_t> buffer(BUFFER_SIZE * CHANNELS);
unsigned int bufferIndex = 0;

std::mutex mtx;

int audioCallback(void* outputBuffer, void* inputBuffer, unsigned int nBufferFrames, double streamTime, RtAudioStreamStatus status, void* userData) {
    mtx.lock();

    int16_t* data = static_cast<int16_t*>(inputBuffer);

    for (unsigned int i = 0; i < nBufferFrames; ++i) {
        buffer[bufferIndex] = data[i];
        bufferIndex = (bufferIndex + 1) % buffer.size();
    }

    mtx.unlock();
    return 0;
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
            std::this_thread::sleep_for(std::chrono::seconds(INTERVAL));
            saveAudio();
        }

        audio.stopStream();
    }
    catch (RtAudioError& e) {
        e.printMessage();
    }
}

void saveAudio() {
    mtx.lock();

    SF_INFO sfinfo;
    sfinfo.samplerate = SAMPLE_RATE;
    sfinfo.channels = CHANNELS;
    sfinfo.format = SF_FORMAT_FLAC | SF_FORMAT_PCM_16;

    auto t = std::time(nullptr);
    auto tm = *std::localtime(&t);
    std::ostringstream oss;
    oss << OUTPUT_DIRECTORY << "/" << std::put_time(&tm, "%Y%m%d-%H%M%S") << ".flac";
    std::string filename = oss.str();

    SNDFILE* outfile = sf_open(filename.c_str(), SFM_WRITE, &sfinfo);

    sf_write_short(outfile, buffer.data(), buffer.size());

    sf_close(outfile);

    mtx.unlock();
}

int main() {
    RtAudio audio;

    if (audio.getDeviceCount() < 1) {
        std::cout << "\nNo audio devices found!" << std::endl;
        exit(1);
    }

    audioStream(audio);

    if (audio.isStreamOpen()) audio.closeStream();

    return 0;
}
