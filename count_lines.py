#!/usr/bin/env python3
import os
import glob

def count_lines_in_file(filepath):
    """Count lines in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for line in f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return 0

def main():
    modules_dir = r'e:\git\earth_biometrics\project-bees-knees\beehub\python\src\modules'
    pattern = os.path.join(modules_dir, '*.py')
    files = glob.glob(pattern)
    
    total_lines = 0
    file_counts = []
    
    print("Line counts for Python files in modules directory:")
    print("=" * 60)
    
    for filepath in sorted(files):
        filename = os.path.basename(filepath)
        line_count = count_lines_in_file(filepath)
        file_counts.append((filename, line_count))
        total_lines += line_count
        print(f"{filename:<35} {line_count:>6} lines")
    
    print("=" * 60)
    print(f"{'Total:':<35} {total_lines:>6} lines")
    print(f"Number of files: {len(files)}")

if __name__ == "__main__":
    main()
