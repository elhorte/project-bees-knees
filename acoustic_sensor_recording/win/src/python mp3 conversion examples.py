# background



def numpy_to_mp3(np_array, sample_rate):
    # Ensure the array is formatted as int16
    int_array = np_array.astype(np.int16)

    # Convert the array to bytes
    byte_array = int_array.tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        # raw audio data (bytes)
        data=byte_array,
        # 2 byte (16 bit) samples
        sample_width=2,
        # 48000 frame rate
        frame_rate=sample_rate,
        # stereo audio
        channels=2
    )

    # Export the AudioSegment instance as an MP3 file
    audio_segment.export("output.mp3", format="mp3")

'''
'''
import numpy as np
from scipy.signal import resample_poly
from pydub import AudioSegment

def numpy_to_mp3(np_array, orig_sample_rate, target_sample_rate, vbr_quality="2"):
    int_array = np_array.astype(np.int16)
    int_array = int_array.T
    # Resample each channel
    resampled_array = np.array([
        resample_poly(ch, target_sample_rate, orig_sample_rate)
        for ch in int_array
    ])
    # Transpose the array back to the original shape and convert to bytes
    byte_array = resampled_array.T.astype(np.int16).tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        # raw audio data (bytes)
        data=byte_array,
        # 2 byte (16 bit) samples
        sample_width=2,
        # target frame rate
        frame_rate=target_sample_rate,
        # stereo audio
        channels=2
    )

    # Export the AudioSegment instance as an MP3 file with VBR
    audio_segment.export("output.mp3", format="mp3", parameters=["-q:a", vbr_quality])

# Usage example:
# Assume 'audio_data' is your original data
# audio_data = 

numpy_to_mp3(audio_data, orig_sample_rate=48000, target_sample_rate=44100, vbr_quality="2")

'''The actual MP3 conversion is performed by the LAME encoder. PyDub, the Python library you're using, provides a convenient and Pythonic interface to this process, but the heavy lifting is done by LAME itself.

Here's a brief explanation of the process:

1. PyDub takes the audio data and formats it into a form that can be understood by the LAME encoder. This includes converting the data into bytes and setting the appropriate sample width, frame rate, and number of channels.
2. PyDub calls the LAME encoder with the appropriate parameters, including the quality setting for Variable Bitrate (VBR) encoding.
3. LAME encodes the audio data into the MP3 format. This involves several steps, including quantization, Huffman coding, and adding MP3 headers and metadata.
4. The encoded MP3 data is then written to a file, which is what the `AudioSegment.export` function does in your Python script.

So, while your Python script is managing the process, the actual conversion from raw audio data to the MP3 format is done by LAME. This is why you need to have the LAME encoder installed on your system to be able to export MP3 files with PyDub.'''

'''First, make sure your np_array is a 2D array where each row is a channel of audio and each column is a sample. In stereo audio, there should be two rows. If your audio is mono but in a 2D array, make sure it has two identical rows. If your np_array is a 1D array, you need to convert it to the correct 2D format before resampling.

Next, the length of the output can be influenced by how the resampling is done. Both the resample function from scipy.signal and the resample function from librosa change the number of samples in the signal, which directly impacts the duration of the output. The ratio between the original and target sample rates determines the new number of samples.

Lastly, let's consider the export parameters used for MP3 encoding. VBR (Variable Bit Rate) encoding allows the bit rate to vary depending on the complexity of the audio, but the duration should not be affected.'''

''' print("Array Type: ", type(audio_data))
    print("Data Type: ", audio_data.dtype)
    print("Array Shape: ", audio_data.shape)
    print("Number of dimensions: ", audio_data.ndim)
    print("Total Number of elements: ", audio_data.size)
    print("First few elements: ", audio_data[:10])
    print(".....transposing array......")
    audio_data = np_array.T
    print("Array Type: ", type(audio_data))
    print("Data Type: ", audio_data.dtype)
    print("Array Shape: ", audio_data.shape)
    print("Number of dimensions: ", audio_data.ndim)
    print("Total Number of elements: ", audio_data.size)
    print("First few elements: ", audio_data[:10])
    print(".....transposing array......")'''


#
# convert audio to mp3 and save to file
#

def numpy_to_mp3(np_array, orig_sample_rate=192000, target_sample_rate=48000):

    int_array = np_array.astype(np.int16)
    int_array = int_array.T
    # Resample each channel
    resampled_array = np.array([
        resample_poly(ch, target_sample_rate, orig_sample_rate)
        for ch in int_array
    ])
    # Transpose the array back to the original shape and convert to bytes
    byte_array = resampled_array.T.astype(np.int16).tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        data=byte_array,
        sample_width=2,
        frame_rate=target_sample_rate,
        channels=2
    )

    # Export the AudioSegment instance as an MP3 file with VBR
    audio_segment.export("output.mp3", format="mp3", parameters=["-q:a", "0"])
'''
'''
import numpy as np
from scipy.signal import resample_poly
from pydub import AudioSegment

def numpy_to_mp3(np_array, orig_sample_rate=192000, target_sample_rate=48000):
    #np_array = np_array.T

    # Ensure the array is formatted as float64
    float_array = np_array.astype(np.float64)

    # Transpose the array to have channels as the first dimension
    float_array = float_array.T

    # Resample each channel
    resampled_array = np.array([
        resample_poly(ch, target_sample_rate, orig_sample_rate)
        for ch in float_array
    ])

    # Transpose the array back to the original shape and convert to int16
    int_array = resampled_array.T.astype(np.int16)

    # Convert the array to bytes
    byte_array = int_array.tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        data=byte_array,
        sample_width=2,
        frame_rate=target_sample_rate,
        channels=2
    )

    # Export the AudioSegment instance as an MP3 file with VBR
    audio_segment.export("output.mp3", format="mp3", parameters=["-q:a", "0"])

'''
# notes on python environments

The issue seems to be with the `llvmlite` package which is a dependency of `numba`, and `numba` is in turn a dependency of `resampy`. This kind of error usually occurs due to issues with the Python environment and package installation, or the specific versions of the packages and their compatibility with each other.

Here are a few steps you can try to resolve this issue:

1. **Reinstall llvmlite and numba:** Try uninstalling `llvmlite` and `numba` and reinstalling them. This can sometimes solve the problem if the issue was caused by a broken or incomplete installation.

   ```shell
   pip uninstall llvmlite numba
   pip install llvmlite numba
   ```

2. **Create a new virtual environment:** Sometimes Python package issues can be caused by conflicts between different packages installed in the same environment. Creating a new virtual environment can help ensure that there are no conflicting packages.

   ```shell
   python -m venv env
   source env/bin/activate  # On Windows use `env\Scripts\activate`
   pip install resampy
   ```

3. **Downgrade Python version:** As of my knowledge cutoff in September 2021, `numba` (and by extension `llvmlite`) were fully compatible with Python 3.7. If neither of the above solutions work, you might try downgrading your Python version to 3.7 and see if that resolves the issue.

4. **Consult the Numba issue tracker:** If none of the above suggestions work, there may be a specific issue with your system configuration that is causing this problem. In this case, you could check the [Numba issue tracker](https://github.com/numba/numba/issues) to see if anyone else has reported a similar problem and if there are any suggested solutions.

Remember to perform these steps in the same Python environment you are using to run your script.'''


'''It seems like you're using PowerShell. The `source` command doesn't exist in PowerShell. In PowerShell, you should use the dot sourcing operator `.`, instead. 

Please try the following command:
```bash
. .\env\Scripts\activate
```

If that doesn't work, you could also try the following command:
```bash
.\env\Scripts\activate
``` 

This will activate your virtual environment. If it's successful, you should see the name of your virtual environment (in this case `env`) at the beginning of your shell prompt. 

Once you've activated your environment, you can install your packages into the virtual environment.'''

'''This error means that your system's execution policy is restricting you from running the script. PowerShell has a feature called "execution policies" to improve security by controlling the conditions under which PowerShell loads configuration files and runs scripts. You can temporarily change the execution policy in your current PowerShell session to allow scripts to run by typing the following command:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process
```
This changes the execution policy to `Unrestricted` for the current PowerShell process only. The change affects only the current session and the policy will revert back to its previous state when you close the session.
After running the above command, you should be able to activate your virtual environment with:

```powershell
. .\env\Scripts\activate
```
Alternatively, if you want to change the execution policy permanently (which is not generally recommended for security reasons), you can use the `Set-ExecutionPolicy` cmdlet with the `-Scope` parameter set to `CurrentUser` or `LocalMachine`, like so:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope CurrentUser
```
Remember, if you're going to change this setting permanently, it's generally safer to set it to `RemoteSigned` instead of `Unrestricted`. `RemoteSigned` means that as long as a script has been signed by a trusted publisher, it will run. Unsigned scripts downloaded from the Internet won't run unless they're unblocked first.'''
