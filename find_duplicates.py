#!/usr/bin/env python3
import ast
import os

def find_duplicate_functions(filepath):
    """Find duplicate function definitions in a file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=filepath)
        
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    'name': node.name,
                    'line': node.lineno,
                    'args': [arg.arg for arg in node.args.args]
                })
        
        # Find duplicates
        func_names = {}
        for func in functions:
            name = func['name']
            if name not in func_names:
                func_names[name] = []
            func_names[name].append(func)
        
        duplicates = {name: funcs for name, funcs in func_names.items() if len(funcs) > 1}
        
        return {
            'file': os.path.basename(filepath),
            'all_functions': functions,
            'duplicates': duplicates,
            'total_functions': len(functions)
        }
        
    except Exception as e:
        return {
            'file': os.path.basename(filepath),
            'error': str(e)
        }

def main():
    # Analyze specific problematic files
    problem_files = [
        r'e:\git\eb\project-bees-knees\beehub\python\src\modules\plotting.py',
        r'e:\git\eb\project-bees-knees\beehub\python\src\modules\audio_tools.py',
        r'e:\git\eb\project-bees-knees\beehub\python\src\modules\system_utils.py',
        r'e:\git\eb\project-bees-knees\beehub\python\src\modules\audio_processing.py'
    ]
    
    print('DUPLICATE FUNCTION ANALYSIS')
    print('=' * 60)
    
    for filepath in problem_files:
        if os.path.exists(filepath):
            result = find_duplicate_functions(filepath)
            
            print(f'\n{result["file"]}:')
            
            if 'error' in result:
                print(f'  ERROR: {result["error"]}')
                continue
            
            print(f'  Total functions: {result["total_functions"]}')
            
            if result['duplicates']:
                print(f'  DUPLICATE FUNCTIONS:')
                for func_name, instances in result['duplicates'].items():
                    print(f'    {func_name}: {len(instances)} instances')
                    for instance in instances:
                        args_str = ', '.join(instance['args'])
                        print(f'      Line {instance["line"]}: def {func_name}({args_str})')
            else:
                print('  No duplicate functions found')
        else:
            print(f'\n{os.path.basename(filepath)}: FILE NOT FOUND')

if __name__ == "__main__":
    main()
