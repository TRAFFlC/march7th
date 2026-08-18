"""
项目代码行数统计工具
"""
import os
from pathlib import Path
from collections import defaultdict

def count_lines(project_dir: str, exclude_dirs: list = None, exclude_files: list = None):
    exclude_dirs = exclude_dirs or ['node_modules', '.git', '__pycache__', '.pytest_cache', 
                                     'venv', 'env', '.venv', 'dist', 'build', '.idea', '.vscode',
                                     'logs', 'logs_archive', 'persona_db']
    exclude_files = exclude_files or ['.pyc', '.pyo', '.exe', '.dll', '.so', '.dylib',
                                       '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg',
                                       '.wav', '.mp3', '.mp4', '.avi', '.mov',
                                       '.zip', '.tar', '.gz', '.rar',
                                       '.pth', '.ckpt', '.pt', '.bin']
    
    stats = defaultdict(lambda: {'files': 0, 'lines': 0, 'blank': 0, 'comments': 0})
    total = {'files': 0, 'lines': 0, 'blank': 0, 'comments': 0}
    
    project_path = Path(project_dir)
    
    for file_path in project_path.rglob('*'):
        if not file_path.is_file():
            continue
        
        rel_path = file_path.relative_to(project_path)
        
        if any(excluded in rel_path.parts for excluded in exclude_dirs):
            continue
        
        if any(str(file_path).endswith(ext) for ext in exclude_files):
            continue
        
        ext = file_path.suffix.lower()
        if not ext:
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except:
            continue
        
        file_lines = len(lines)
        blank_lines = sum(1 for line in lines if not line.strip())
        
        comment_chars = {'.py': '#', '.js': '//', '.ts': '//', '.vue': '//', 
                        '.java': '//', '.c': '//', '.cpp': '//', '.h': '//',
                        '.css': '/*', '.scss': '//', '.html': '<!--',
                        '.sh': '#', '.bat': 'REM', '.ps1': '#',
                        '.json': None, '.md': None, '.yaml': '#', '.yml': '#'}
        
        comment_char = comment_chars.get(ext)
        comment_lines = 0
        if comment_char:
            for line in lines:
                stripped = line.strip()
                if stripped.startswith(comment_char):
                    comment_lines += 1
        
        stats[ext]['files'] += 1
        stats[ext]['lines'] += file_lines
        stats[ext]['blank'] += blank_lines
        stats[ext]['comments'] += comment_lines
        
        total['files'] += 1
        total['lines'] += file_lines
        total['blank'] += blank_lines
        total['comments'] += comment_lines
    
    return stats, total

def print_report(stats: dict, total: dict):
    print("\n" + "=" * 60)
    print("📊 项目代码统计报告")
    print("=" * 60)
    
    print("\n📁 按文件类型统计:")
    print("-" * 60)
    print(f"{'类型':<10} {'文件数':>8} {'总行数':>10} {'空白行':>10} {'注释行':>10}")
    print("-" * 60)
    
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['lines'], reverse=True)
    
    for ext, data in sorted_stats:
        if data['files'] > 0:
            print(f"{ext:<10} {data['files']:>8} {data['lines']:>10} {data['blank']:>10} {data['comments']:>10}")
    
    print("-" * 60)
    print(f"{'总计':<10} {total['files']:>8} {total['lines']:>10} {total['blank']:>10} {total['comments']:>10}")
    print("=" * 60)
    
    code_lines = total['lines'] - total['blank'] - total['comments']
    print(f"\n📈 有效代码行数: {code_lines:,} 行")
    print(f"📈 代码占比: {code_lines/total['lines']*100:.1f}%" if total['lines'] > 0 else "")

if __name__ == "__main__":
    project_dir = os.path.dirname(os.path.abspath(__file__))
    stats, total = count_lines(project_dir)
    print_report(stats, total)
