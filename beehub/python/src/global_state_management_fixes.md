# Global State Management Fixes for BMAR_gem2.py

## Summary of Changes Made

### 1. Enhanced BmarApp Class
- Added all missing instance variables that were previously global
- Added proper initialization of all state variables
- Encapsulated thread management, process management, and configuration

### 2. Application Instance Pattern
- Created global `app_instance` variable for signal handlers
- Added `get_app_instance()` and `set_app_instance()` helper functions
- Updated signal handlers to use app instance

### 3. Function Updates Needed
The following functions still need to be updated to accept `app` parameter instead of using global variables:

#### High Priority (frequently used):
- `show_audio_device_info_for_SOUND_IN_OUT()` → `show_audio_device_info_for_SOUND_IN_OUT(app)`
- `check_stream_status()` → `check_stream_status(app, stream_duration)`
- `change_monitor_channel()` - remove `global monitor_channel`
- `toggle_vu_meter()` - use `app.active_processes` instead of global
- `toggle_intercom_m()` - use app instance variables
- `kill_worker_threads()` → `kill_worker_threads(app)`

#### Medium Priority:
- `get_enabled_mic_locations()` → `get_enabled_mic_locations(app)`
- `find_file_of_type_with_offset()` functions
- Various plotting functions

### 4. Remaining Global Variables (Acceptable)
These can remain global as they are constants or singletons:
- `platform_manager` (singleton)
- `FFT_BINS`, `FFT_BW`, `FULL_SCALE` (constants)
- `app_instance` (singleton pattern for signal handlers)
- `lock` (global thread lock)

### 5. Variables Successfully Moved to BmarApp
- All audio interface info (make_name, model_name, etc.)
- Recording variables (continuous_start_index, event_start_index, etc.)
- Thread and process references
- Event flags and queues
- Misc state (monitor_channel, file_offset, etc.)

## Benefits of These Changes
1. **Better Encapsulation**: State is contained within the app instance
2. **Thread Safety**: Easier to manage state across threads
3. **Testing**: Can create multiple app instances for testing
4. **Debugging**: Clear ownership of state variables
5. **Maintainability**: Easier to understand data flow

## Next Steps
1. Update remaining function signatures to accept `app` parameter
2. Remove remaining `global` statements
3. Update function calls throughout the codebase
4. Test to ensure no functionality is broken

The core architecture improvement is complete - the app now uses proper encapsulation
with an instance pattern that supports signal handlers and multi-threading.
