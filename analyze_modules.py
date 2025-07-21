#!/usr/bin/env python3
import ast
import os
import glob

def analyze_python_file(filepath):
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content, filename=filepath)
        
        # Find imports
        imports = []
        functions = []
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.append(f'{node.module}.{alias.name}' if node.module else alias.name)
            elif isinstance(node, ast.FunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
        
        # Check for duplicate function names
        func_counts = {}
        for func in functions:
            func_counts[func] = func_counts.get(func, 0) + 1
        
        duplicates = {k: v for k, v in func_counts.items() if v > 1}
        if duplicates:
            issues.append(f'Duplicate functions: {duplicates}')
        
        # Basic syntax errors check
        if 'return Falses' in content:
            issues.append('Typo: return Falses should be return False')
        
        if 'import sys' in content and 'sys.' not in content:
            issues.append('Unused import: sys')
            
        return {
            'file': os.path.basename(filepath),
            'imports': imports,
            'functions': functions,
            'classes': classes,
            'issues': issues,
            'lines': len(content.splitlines())
        }
    except Exception as e:
        return {
            'file': os.path.basename(filepath),
            'error': str(e),
            'issues': [f'Parse error: {e}']
        }

def main():
    # Analyze all Python files in modules
    modules_dir = r'e:\git\eb\project-bees-knees\beehub\python\src\modules'
    pattern = os.path.join(modules_dir, '*.py')
    files = glob.glob(pattern)

    print('PYTHON MODULE ANALYSIS')
    print('=' * 60)

    all_functions = {}
    all_issues = []

    for filepath in sorted(files):
        result = analyze_python_file(filepath)
        
        print(f'\n{result["file"]}:')
        
        if 'error' in result:
            print(f'  ERROR: {result["error"]}')
            continue
        
        print(f'  Lines: {result["lines"]}')
        print(f'  Functions: {len(result["functions"])}')
        print(f'  Classes: {len(result["classes"])}')
        
        if result['issues']:
            print(f'  ISSUES:')
            for issue in result['issues']:
                print(f'    - {issue}')
                all_issues.append(f'{result["file"]}: {issue}')
        
        # Track function names across modules for duplicates
        for func in result['functions']:
            if func not in all_functions:
                all_functions[func] = []
            all_functions[func].append(result['file'])

    print(f'\n\nCROSS-MODULE ANALYSIS')
    print('=' * 60)

    # Find functions defined in multiple modules
    duplicate_funcs = {k: v for k, v in all_functions.items() if len(v) > 1}
    if duplicate_funcs:
        print('Functions defined in multiple modules:')
        for func, files in duplicate_funcs.items():
            print(f'  {func}: {files}')

    print(f'\n\nSUMMARY OF ALL ISSUES')
    print('=' * 60)
    if all_issues:
        for issue in all_issues:
            print(f'  - {issue}')
    else:
        print('  No issues found in basic analysis')

if __name__ == "__main__":
    main()
