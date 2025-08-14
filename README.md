# project-bees-knees

Earth biometric monitoring project

BMAR -- Biometric Monitoring and Analysis for Research

This project is for a data gathering software system for capturing biometric data from a multiplicity of sensor types. The intended sensor types include acoustic microphones, still camera images, video streams, gas sensors, water sensors, among others. Captured data can be saved in any file format to designated local or remote storage.

The system is built on a circular buffer for sensor data capture which allows the system to capture data up to the length of the buffer prior to a triggering event. Trigger events can be based on any algorithm such as spectral events, amplitude and duration, FFT bin pattern, etc. Once triggered, the circular buffer is save to the extend found in the config module and will continue to record after the trigger event for the duration set.

In the case of audio sensor data, the signal can be sampled at any rate up to 192k samples per second (SPS) to allow for trigger detection events with frequency components up to Nyquest limit of the sample rate. The sensor data saved upon a triggered even can be save at any data rate at or less that the sample rate of the circular buffer. The primary data is typically saved in the FLAC or ALAC MPEG format, both of which are lossless. Likewise, the primary audio signal can be saves as a continuous data stream not dependent on an audio trigger.

A secondary audio stream is generated as a continuous "confidence" record of audio events and is typically saved in a low-quality format such as MP3.

The BMAR system runs from the command line (or shell script) of a remote computing device. Access to the device is via ssh and hense has limited bandwidth for monitoring activity. In order to provide rich status information back to a control agent (or human), a keystroke-driven suite of monitoring functions is provided as follows:

BMAR Controls:

  'r' - Start/stop recording

  's' - Spectrogram (one-shot with GUI)

  'o' - Oscilloscope (10s capture with GUI)

  't' - Threads (list all)

  'v' - VU meter (independent, start before intercom for combo mode)

  'i' - Intercom (audio monitoring)

  'd' - Current audio device

  'D' - List detailed audio devices

  'p' - Performance monitor

  'P' - Continuous performance monitor

  'f' - FFT analysis (10s with progress bar)

  'c' - Configuration

  'h' - Help

 'q' - Quit

 '^' - Toggle between BMAR keyboard mode and normal terminal

The graphic image oriented functions save a 'png' file to a cloud locations to be retrieved and analyses remotely.

The current code base has a problem with audio file saving. The analysis of the saved audio data shows a non-audio waveform that does not represent the signal captured by the system.

Please examine the audio processing from input to circular buffer to file saving of both the primary and audio monitoring audio.
