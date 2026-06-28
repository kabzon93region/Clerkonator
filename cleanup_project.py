# -*- coding: utf-8 -*-
"""
Project Cleanup Script - Removes unused files from project
Keeps only files that are actually used by the application
"""

import os
import shutil
from pathlib import Path

def cleanup_project():
    """Clean up project by removing unused files"""
    
    print("=" * 60)
    print("Project Cleanup - Removing Unused Files")
    print("=" * 60)
    
    # Files to remove (unused by current application)
    files_to_remove = [
        # Test files
        "test_stt.py",
        "test_audio_features.py", 
        "test_convert_feature.py",
        "test_stt.cmd",
        "test_audio.cmd",
        "test_convert.cmd",
        
        # Development utilities
        "check_encoding.py",
        "convert_line_endings.py",
        "fix_cyrillic.py",
        "convert_line_endings.cmd",
        
        # Old/unused GUI files
        "gui_app.py",
        
        # Version management
        "version_manager.py",
        "create_version.cmd",
        "create_release.py",
        "create_clean_release.py",
        "create_release.cmd",
        "create_clean_release.cmd",
        
        # Release info files
        "release_info.json",
        "clean_release_info.json",
        
        # This cleanup script itself (will be removed last)
        "cleanup_project.py",
    ]
    
    # Directories to remove (if empty after file removal)
    dirs_to_check = [
        "scripts",  # If it exists and is empty
    ]
    
    removed_files = 0
    removed_dirs = 0
    
    print("Removing unused files...")
    print()
    
    # Remove files
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"  Removed: {file_path}")
                removed_files += 1
            except Exception as e:
                print(f"  Error removing {file_path}: {e}")
        else:
            print(f"  Not found: {file_path}")
    
    print()
    print("Checking directories...")
    
    # Remove empty directories
    for dir_path in dirs_to_check:
        if os.path.exists(dir_path):
            try:
                if not os.listdir(dir_path):  # Check if empty
                    os.rmdir(dir_path)
                    print(f"  Removed empty directory: {dir_path}")
                    removed_dirs += 1
                else:
                    print(f"  Directory not empty: {dir_path}")
            except Exception as e:
                print(f"  Error removing directory {dir_path}: {e}")
    
    # Clean up __pycache__ directories
    print()
    print("Cleaning up Python cache...")
    cache_removed = 0
    
    for root, dirs, files in os.walk("."):
        if "__pycache__" in dirs:
            cache_dir = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(cache_dir)
                print(f"  Removed cache: {cache_dir}")
                cache_removed += 1
            except Exception as e:
                print(f"  Error removing cache {cache_dir}: {e}")
    
    # Remove .pyc files
    pyc_removed = 0
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".pyc"):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"  Removed .pyc: {file_path}")
                    pyc_removed += 1
                except Exception as e:
                    print(f"  Error removing .pyc {file_path}: {e}")
    
    print()
    print("=" * 60)
    print("CLEANUP COMPLETED!")
    print("=" * 60)
    print(f"Files removed: {removed_files}")
    print(f"Directories removed: {removed_dirs}")
    print(f"Cache directories removed: {cache_removed}")
    print(f".pyc files removed: {pyc_removed}")
    print()
    print("Project cleaned up successfully!")
    print("Only essential files remain.")
    
    return removed_files + removed_dirs + cache_removed + pyc_removed

def show_remaining_files():
    """Show remaining files in project"""
    print()
    print("=" * 60)
    print("REMAINING FILES IN PROJECT")
    print("=" * 60)
    
    # Core files
    core_files = [
        "main.py",
        "requirements.txt", 
        "config.json",
        "setup.cmd",
        "run.cmd",
        "README.md",
        "ЗАПУСК.md",
    ]
    
    print("Core files:")
    for file in core_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} (missing)")
    
    # Module directories
    modules = ["gui", "audio", "stt", "utils", "docs"]
    print("\nModule directories:")
    for module in modules:
        if os.path.exists(module):
            files = [f for f in os.listdir(module) if f.endswith('.py')]
            print(f"  ✓ {module}/ ({len(files)} Python files)")
        else:
            print(f"  ✗ {module}/ (missing)")
    
    # Other files
    other_files = [f for f in os.listdir(".") if f.endswith(('.py', '.cmd', '.txt', '.md', '.json'))]
    if other_files:
        print("\nOther files:")
        for file in sorted(other_files):
            if file not in core_files:
                print(f"  ? {file}")

if __name__ == "__main__":
    try:
        total_removed = cleanup_project()
        show_remaining_files()
        print(f"\n[OK] Cleanup completed! {total_removed} items removed.")
    except Exception as e:
        print(f"\n[ERROR] Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        input("\nPress Enter to exit...")
    except (EOFError, KeyboardInterrupt):
        pass
