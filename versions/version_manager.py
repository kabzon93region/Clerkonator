#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер версий для Clerkonator
Локальная система управления версиями
"""

import os
import shutil
import json
import datetime
from pathlib import Path
from typing import Dict, List, Optional


class VersionManager:
    """Менеджер локальных версий проекта"""
    
    def __init__(self, project_root: str = "."):
        """Инициализация менеджера версий"""
        self.project_root = Path(project_root).resolve()
        self.versions_dir = self.project_root / "versions"
        self.metadata_file = self.versions_dir / "versions.json"
        
        # Создаем папку версий если не существует
        self.versions_dir.mkdir(exist_ok=True)
        
        # Загружаем метаданные версий
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Загрузка метаданных версий"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки метаданных: {e}")
        
        return {
            "versions": [],
            "current_version": None,
            "last_updated": None
        }
    
    def _save_metadata(self):
        """Сохранение метаданных версий"""
        try:
            self.metadata["last_updated"] = datetime.datetime.now().isoformat()
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения метаданных: {e}")
    
    def create_version(self, version: str, description: str = "", 
                      author: str = "", tags: List[str] = None) -> bool:
        """Создание новой версии проекта"""
        try:
            # Проверяем формат версии (семантическое версионирование)
            if not self._validate_version(version):
                print(f"Неверный формат версии: {version}")
                return False
            
            # Проверяем, не существует ли уже такая версия
            if self.version_exists(version):
                print(f"Версия {version} уже существует")
                return False
            
            # Создаем папку для версии
            version_dir = self.versions_dir / f"v{version}"
            version_dir.mkdir(exist_ok=True)
            
            # Копируем файлы проекта (исключая служебные папки)
            excluded_dirs = {
                'versions', '__pycache__', '.git', 'venv', 
                'data', '.pytest_cache', 'models'
            }
            
            excluded_files = {
                '*.pyc', '*.pyo', '*.pyd', '.DS_Store', 'Thumbs.db'
            }
            
            copied_files = self._copy_project_files(version_dir, excluded_dirs, excluded_files)
            
            # Создаем метаданные версии
            version_metadata = {
                "version": version,
                "description": description,
                "author": author,
                "tags": tags or [],
                "created_at": datetime.datetime.now().isoformat(),
                "files_count": len(copied_files),
                "files": copied_files
            }
            
            # Сохраняем метаданные версии
            version_meta_file = version_dir / "version.json"
            with open(version_meta_file, 'w', encoding='utf-8') as f:
                json.dump(version_metadata, f, ensure_ascii=False, indent=2)
            
            # Обновляем общие метаданные
            self.metadata["versions"].append(version_metadata)
            self.metadata["current_version"] = version
            self._save_metadata()
            
            print(f"Версия {version} создана успешно")
            print(f"Папка: {version_dir}")
            print(f"Файлов скопировано: {len(copied_files)}")
            
            return True
            
        except Exception as e:
            print(f"Ошибка создания версии: {e}")
            return False
    
    def _validate_version(self, version: str) -> bool:
        """Проверка формата версии"""
        import re
        pattern = r'^\d+\.\d+\.\d+$'
        return bool(re.match(pattern, version))
    
    def _copy_project_files(self, target_dir: Path, excluded_dirs: set, 
                           excluded_files: set) -> List[str]:
        """Копирование файлов проекта"""
        copied_files = []
        
        for item in self.project_root.iterdir():
            if item.name in excluded_dirs:
                continue
            
            if item.is_file():
                # Проверяем исключения для файлов
                if any(item.name.endswith(ext.replace('*', '')) for ext in excluded_files):
                    continue
                
                target_file = target_dir / item.name
                shutil.copy2(item, target_file)
                copied_files.append(str(item.relative_to(self.project_root)))
            
            elif item.is_dir() and item.name not in excluded_dirs:
                # Копируем папку рекурсивно
                target_subdir = target_dir / item.name
                target_subdir.mkdir(exist_ok=True)
                
                subdir_files = self._copy_directory_recursive(item, target_subdir, excluded_dirs, excluded_files)
                copied_files.extend([f"{item.name}/{f}" for f in subdir_files])
        
        return copied_files
    
    def _copy_directory_recursive(self, src_dir: Path, target_dir: Path, 
                                 excluded_dirs: set, excluded_files: set) -> List[str]:
        """Рекурсивное копирование папки"""
        copied_files = []
        
        for item in src_dir.iterdir():
            if item.name in excluded_dirs:
                continue
            
            if item.is_file():
                if any(item.name.endswith(ext.replace('*', '')) for ext in excluded_files):
                    continue
                
                target_file = target_dir / item.name
                shutil.copy2(item, target_file)
                copied_files.append(item.name)
            
            elif item.is_dir():
                target_subdir = target_dir / item.name
                target_subdir.mkdir(exist_ok=True)
                
                subdir_files = self._copy_directory_recursive(item, target_subdir, excluded_dirs, excluded_files)
                copied_files.extend([f"{item.name}/{f}" for f in subdir_files])
        
        return copied_files
    
    def version_exists(self, version: str) -> bool:
        """Проверка существования версии"""
        return any(v["version"] == version for v in self.metadata["versions"])
    
    def list_versions(self) -> List[Dict]:
        """Получение списка всех версий"""
        return sorted(self.metadata["versions"], 
                     key=lambda x: [int(i) for i in x["version"].split('.')], 
                     reverse=True)
    
    def get_version_info(self, version: str) -> Optional[Dict]:
        """Получение информации о версии"""
        for v in self.metadata["versions"]:
            if v["version"] == version:
                return v
        return None
    
    def restore_version(self, version: str) -> bool:
        """Восстановление версии (копирование в основную папку)"""
        try:
            version_dir = self.versions_dir / f"v{version}"
            if not version_dir.exists():
                print(f"❌ Версия {version} не найдена")
                return False
            
            # Создаем резервную копию текущего состояния
            backup_dir = self.project_root / f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"🔄 Создание резервной копии в {backup_dir}")
            
            # Копируем текущее состояние в backup
            self._copy_project_files(backup_dir, {'versions', '__pycache__', '.git'}, {'*.pyc'})
            
            # Восстанавливаем версию
            print(f"🔄 Восстановление версии {version}")
            for item in version_dir.iterdir():
                if item.name == "version.json":
                    continue
                
                target = self.project_root / item.name
                if item.is_file():
                    shutil.copy2(item, target)
                elif item.is_dir():
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(item, target)
            
            print(f"✅ Версия {version} восстановлена")
            print(f"💾 Резервная копия: {backup_dir}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка восстановления версии: {e}")
            return False
    
    def delete_version(self, version: str) -> bool:
        """Удаление версии"""
        try:
            version_dir = self.versions_dir / f"v{version}"
            if not version_dir.exists():
                print(f"❌ Версия {version} не найдена")
                return False
            
            # Удаляем папку версии
            shutil.rmtree(version_dir)
            
            # Удаляем из метаданных
            self.metadata["versions"] = [v for v in self.metadata["versions"] if v["version"] != version]
            
            if self.metadata["current_version"] == version:
                self.metadata["current_version"] = None
            
            self._save_metadata()
            
            print(f"✅ Версия {version} удалена")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка удаления версии: {e}")
            return False
    
    def get_current_version(self) -> Optional[str]:
        """Получение текущей версии"""
        return self.metadata.get("current_version")
    
    def set_current_version(self, version: str) -> bool:
        """Установка текущей версии"""
        if not self.version_exists(version):
            print(f"❌ Версия {version} не найдена")
            return False
        
        self.metadata["current_version"] = version
        self._save_metadata()
        print(f"✅ Текущая версия установлена: {version}")
        return True
    
    def create_changelog(self) -> str:
        """Создание changelog из версий"""
        changelog = "# Changelog\n\n"
        changelog += "Все значимые изменения в проекте Clerkonator документируются в этом файле.\n\n"
        changelog += "Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/).\n\n"
        
        versions = self.list_versions()
        
        for version_info in versions:
            version = version_info["version"]
            created_at = datetime.datetime.fromisoformat(version_info["created_at"]).strftime("%Y-%m-%d")
            description = version_info.get("description", "")
            author = version_info.get("author", "")
            tags = version_info.get("tags", [])
            
            changelog += f"## [{version}] - {created_at}\n\n"
            
            if description:
                changelog += f"### Описание\n{description}\n\n"
            
            if author:
                changelog += f"### Автор\n{author}\n\n"
            
            if tags:
                changelog += f"### Теги\n{', '.join(tags)}\n\n"
            
            changelog += "---\n\n"
        
        return changelog


def main():
    """Главная функция для работы с менеджером версий"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Менеджер версий Clerkonator")
    parser.add_argument("command", choices=["create", "list", "info", "restore", "delete", "changelog"],
                       help="Команда для выполнения")
    parser.add_argument("--version", help="Номер версии")
    parser.add_argument("--description", help="Описание версии")
    parser.add_argument("--author", help="Автор версии")
    parser.add_argument("--tags", nargs="+", help="Теги версии")
    
    args = parser.parse_args()
    
    vm = VersionManager()
    
    if args.command == "create":
        if not args.version:
            print("❌ Необходимо указать версию: --version")
            return
        
        vm.create_version(args.version, args.description or "", args.author or "", args.tags)
    
    elif args.command == "list":
        versions = vm.list_versions()
        print("📋 Список версий:")
        for v in versions:
            created = datetime.datetime.fromisoformat(v["created_at"]).strftime("%Y-%m-%d %H:%M")
            print(f"  v{v['version']} - {created} - {v.get('description', 'Без описания')}")
    
    elif args.command == "info":
        if not args.version:
            print("❌ Необходимо указать версию: --version")
            return
        
        info = vm.get_version_info(args.version)
        if info:
            print(f"📄 Информация о версии {args.version}:")
            print(f"  Описание: {info.get('description', 'Нет')}")
            print(f"  Автор: {info.get('author', 'Не указан')}")
            print(f"  Создана: {datetime.datetime.fromisoformat(info['created_at']).strftime('%Y-%m-%d %H:%M')}")
            print(f"  Файлов: {info.get('files_count', 0)}")
            print(f"  Теги: {', '.join(info.get('tags', []))}")
        else:
            print(f"❌ Версия {args.version} не найдена")
    
    elif args.command == "restore":
        if not args.version:
            print("❌ Необходимо указать версию: --version")
            return
        
        vm.restore_version(args.version)
    
    elif args.command == "delete":
        if not args.version:
            print("❌ Необходимо указать версию: --version")
            return
        
        confirm = input(f"⚠️ Вы уверены, что хотите удалить версию {args.version}? (y/n): ")
        if confirm.lower() == 'y':
            vm.delete_version(args.version)
    
    elif args.command == "changelog":
        changelog = vm.create_changelog()
        changelog_file = Path("CHANGELOG.md")
        with open(changelog_file, 'w', encoding='utf-8') as f:
            f.write(changelog)
        print(f"✅ Changelog создан: {changelog_file}")


if __name__ == "__main__":
    main()
