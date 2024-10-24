#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sounddevice as sd

def query_device_capabilities(device_id=None):
    """
    Query the capabilities of an audio device.
    :param device_id: The ID of the device to query. If None, the default device is used.
    :type device_id: int or None
    """
    try:
        # If device_id is None, this queries the default device.
        device_info = sd.query_devices(device_id)
        
        # Print all information about the device.
        for key, value in device_info.items():
            print(f"{key}: {value}")

        print("")
        # Extract the 'hostapi' value.
        hostapi_id = device_info.get('hostapi')
        list_host_apis(hostapi_id)            

    except Exception as e:
        print(f"An error occurred: {e}")


def list_host_apis(host_api_id=None):
    """
    List all available host APIs or the specified host API and their characteristics.
    :param host_api_id: The ID of the host API to query. If None, all host APIs are listed.
    :type host_api_id: int or None
    """
    host_apis = sd.query_hostapis()
    
    if host_api_id is not None:
        # If a specific host API is requested, print only its information.
        try:
            host_api = host_apis[host_api_id]
            print(f"Host API {host_api_id}:")
            for key, value in host_api.items():
                print(f"  {key}: {value}")
        except IndexError:
            print(f"No host API found with ID {host_api_id}")
    else:
        # If no specific ID is provided, list all host APIs.
        for i, host_api in enumerate(host_apis):
            print(f"Host API {i}:")
            for key, value in host_api.items():
                print(f"  {key}: {value}")
            print("")  # for an empty line between host APIs


def main():
    # Create an argument parser
    parser = argparse.ArgumentParser(description="Query audio device capabilities")

    # Add an argument for the device ID, with a type of int.
    parser.add_argument(
        "device_id",
        type=int,
        help="The ID of the audio device to query",
        nargs="?",  # This makes the argument optional
        default=None,  # This sets the default value to None if the argument isn't provided
    )

    # Parse the command line arguments
    args = parser.parse_args()

    # If a device ID was provided, query that specific device.
    if args.device_id is not None:
        print(f"\nInformation for device with ID {args.device_id}:")
        print("")
        query_device_capabilities(args.device_id)
        print("")
    else:
        print("\nNo device ID provided, listing all devices instead.\n")
        print(sd.query_devices())      
        # Run the function to display all of the host API characteristics
        print("\nListing all hostapi's\n")
        list_host_apis(host_api_id=None)

# The script starts here
if __name__ == "__main__":
    main()
