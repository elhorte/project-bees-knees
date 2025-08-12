#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

def process_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    print(f"Processing file: {file_path}")

    modified_lines = []
    inside_try_block = False
    try_block_indent = None
    temp_try_block = []

    for i, line in enumerate(lines):
        stripped_line = line.lstrip()
        indent_level = len(line) - len(stripped_line)

        # Detect the start of a try block
        if stripped_line.startswith("try:"):
            inside_try_block = True
            try_block_indent = indent_level
            temp_try_block = []
            continue

        # Detect the except block
        if inside_try_block and stripped_line.startswith("except"):
            # Check if the next line contains only 'pass'
            if i + 1 < len(lines):
                next_line = lines[i + 1].lstrip()
                if next_line == "pass\n":
                    # Remove the try/except structure and move the try block code left
                    inside_try_block = False
                    modified_lines.extend(temp_try_block)
                    continue

        # If inside a try block, collect lines
        if inside_try_block:
            if indent_level > try_block_indent:
                temp_try_block.append(line[try_block_indent:])
            else:
                # If indentation decreases, end the try block
                inside_try_block = False
                modified_lines.extend(temp_try_block)
                modified_lines.append(line)
        else:
            # Normal line outside of try/except
            modified_lines.append(line)

    # Write the modified content back to the file
    with open(file_path, 'w') as file:
        file.writelines(modified_lines)

def process_folder(folder_path):
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py'):
                process_file(os.path.join(root, file))

# Specify the folder containing the Python scripts
modules_folder = '.'
process_folder(modules_folder)