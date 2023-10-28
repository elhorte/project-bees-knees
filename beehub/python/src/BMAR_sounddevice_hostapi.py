#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sounddevice as sd

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
    parser = argparse.ArgumentParser(description="List host API characteristics")

    # Add an optional argument for the host API ID.
    parser.add_argument(
        "--id",
        type=int,
        help="The ID of the host API to list. If not provided, all host APIs are listed.",
        default=None,  # Default is to list all host APIs
        dest="host_api_id"  # The parsed argument will be stored as 'host_api_id'
    )

    # Parse the command-line arguments
    args = parser.parse_args()

    # Call the function with the provided command-line arguments
    list_host_apis(args.host_api_id)

# The script starts here
if __name__ == "__main__":
    main()
