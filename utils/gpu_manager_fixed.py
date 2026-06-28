# -*- coding: utf-8 -*-
"""
GPU Manager for Clerkonator - Fixed Version
Improved GPU detection and VRAM monitoring
"""

import subprocess
import re
import psutil
import platform
import os
from typing import Dict, Optional, Tuple

class GPUManager:
    """Менеджер для работы с GPU и видеопамятью"""

    def __init__(self):
        self.system = platform.system()
        self.gpu_info = None
        self.vram_info = None

    def get_gpu_info(self) -> Dict:
        """Получение информации о GPU"""
        if self.system == "Windows":
            return self._get_windows_gpu_info()
        else:
            return {"error": "Поддерживается только Windows"}

    def _get_windows_gpu_info(self) -> Dict:
        """Получение информации о GPU в Windows - улучшенная версия"""
        try:
            # Метод 1: Используем wmic (основной)
            try:
                result = subprocess.run([
                    'wmic', 'path', 'win32_VideoController', 'get', 
                    'Name,AdapterRAM,DriverVersion', '/format:csv'
                ], capture_output=True, text=True, encoding='cp1251', timeout=10)
                
                if result.returncode == 0 and result.stdout.strip():
                    return self._parse_wmic_output(result.stdout)
            except (subprocess.TimeoutExpired, FileNotFoundError, UnicodeDecodeError):
                pass

            # Метод 2: Используем PowerShell (резервный)
            try:
                ps_command = """
                Get-WmiObject -Class Win32_VideoController | 
                Select-Object Name, AdapterRAM, DriverVersion | 
                ConvertTo-Csv -NoTypeInformation
                """
                
                result = subprocess.run([
                    'powershell', '-Command', ps_command
                ], capture_output=True, text=True, encoding='utf-8', timeout=10)
                
                if result.returncode == 0 and result.stdout.strip():
                    return self._parse_powershell_output(result.stdout)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            # Метод 3: Используем dxdiag (последний резерв)
            try:
                return self._get_gpu_info_dxdiag()
            except Exception:
                pass

            return {"error": "Не удалось получить информацию о GPU ни одним из методов"}
            
        except Exception as e:
            return {"error": f"Ошибка получения информации о GPU: {e}"}

    def _parse_wmic_output(self, output: str) -> Dict:
        """Парсинг вывода wmic"""
        lines = output.strip().split('\n')
        gpus = []
        
        for line in lines[1:]:  # Пропускаем заголовок
            if line.strip():
                parts = line.split(',')
                if len(parts) >= 4:
                    name = parts[1].strip()
                    ram = parts[2].strip()
                    driver = parts[3].strip()
                    
                    if name and name != "Name":
                        gpus.append({
                            "name": name,
                            "ram": ram,
                            "driver": driver
                        })
        
        return {"gpus": gpus}

    def _parse_powershell_output(self, output: str) -> Dict:
        """Парсинг вывода PowerShell"""
        lines = output.strip().split('\n')
        gpus = []
        
        for line in lines[1:]:  # Пропускаем заголовок
            if line.strip():
                # PowerShell CSV формат: "Name","AdapterRAM","DriverVersion"
                parts = re.findall(r'"([^"]*)"', line)
                if len(parts) >= 3:
                    name = parts[0].strip()
                    ram = parts[1].strip()
                    driver = parts[2].strip()
                    
                    if name:
                        gpus.append({
                            "name": name,
                            "ram": ram,
                            "driver": driver
                        })
        
        return {"gpus": gpus}

    def _get_gpu_info_dxdiag(self) -> Dict:
        """Получение информации о GPU через dxdiag"""
        try:
            # Создаем временный файл
            temp_file = "temp_dxdiag.txt"
            
            result = subprocess.run([
                'dxdiag', '/t', temp_file
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(temp_file):
                try:
                    with open(temp_file, 'r', encoding='utf-16') as f:
                        content = f.read()
                    
                    # Ищем информацию о GPU
                    gpus = []
                    
                    # Паттерн для поиска GPU
                    gpu_pattern = r'Card name:\s*(.+?)\n'
                    ram_pattern = r'Display Memory:\s*(\d+)\s*MB'
                    
                    gpu_matches = re.findall(gpu_pattern, content, re.IGNORECASE)
                    ram_matches = re.findall(ram_pattern, content, re.IGNORECASE)
                    
                    for i, gpu_name in enumerate(gpu_matches):
                        ram = ram_matches[i] if i < len(ram_matches) else "0"
                        gpus.append({
                            "name": gpu_name.strip(),
                            "ram": ram,
                            "driver": "Unknown"
                        })
                    
                    return {"gpus": gpus}
                    
                finally:
                    # Удаляем временный файл
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            
            return {"error": "dxdiag не вернул данные"}
            
        except Exception as e:
            return {"error": f"Ошибка dxdiag: {e}"}

    def is_intel_iris_xe(self, gpu_name: str) -> bool:
        """Проверка, является ли GPU Intel Iris Xe"""
        if not gpu_name:
            return False
        
        gpu_name_lower = gpu_name.lower()
        return (
            "intel" in gpu_name_lower and 
            "iris" in gpu_name_lower and 
            "xe" in gpu_name_lower
        )

    def get_vram_usage(self) -> Dict:
        """Получение информации об использовании видеопамяти"""
        try:
            # Метод 1: nvidia-smi (для NVIDIA)
            try:
                result = subprocess.run([
                    'nvidia-smi', '--query-gpu=memory.total,memory.used,memory.free',
                    '--format=csv,noheader,nounits'
                ], capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        parts = line.split(', ')
                        if len(parts) >= 3:
                            total = int(parts[0])
                            used = int(parts[1])
                            free = int(parts[2])
                            
                            return {
                                "total_mb": total,
                                "used_mb": used,
                                "free_mb": free,
                                "free_gb": round(free / 1024, 2)
                            }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            # Метод 2: Для Intel GPU - улучшенная оценка
            return self._get_intel_vram_info()
            
        except Exception as e:
            return {"error": f"Ошибка получения информации о VRAM: {e}"}

    def _get_intel_vram_info(self) -> Dict:
        """Получение информации о видеопамяти Intel GPU - улучшенная версия"""
        try:
            # Получаем информацию о системной памяти
            memory = psutil.virtual_memory()
            total_gb = memory.total / (1024**3)
            available_gb = memory.available / (1024**3)
            
            # Для Intel Iris Xe обычно резервируется 1-4GB системной памяти
            # как видеопамять (shared memory)
            if total_gb >= 16:
                # Для систем с 16GB+ RAM
                estimated_vram_gb = 4.0
            elif total_gb >= 8:
                # Для систем с 8-16GB RAM
                estimated_vram_gb = 2.0
            else:
                # Для систем с менее 8GB RAM
                estimated_vram_gb = 1.0
            
            # Оценка свободной видеопамяти (70% от общей)
            estimated_free_gb = estimated_vram_gb * 0.7
            
            return {
                "total_mb": int(estimated_vram_gb * 1024),
                "used_mb": int(estimated_vram_gb * 1024 * 0.3),
                "free_mb": int(estimated_free_gb * 1024),
                "free_gb": round(estimated_free_gb, 2),
                "estimated": True,
                "note": f"Оценка для Intel Iris Xe (система: {total_gb:.1f}GB RAM)"
            }
            
        except Exception as e:
            return {"error": f"Ошибка получения информации о Intel VRAM: {e}"}

    def can_use_gpu(self) -> Tuple[bool, str]:
        """Проверка возможности использования GPU"""
        try:
            # Получаем информацию о GPU
            gpu_info = self.get_gpu_info()
            
            if "error" in gpu_info:
                return False, f"Ошибка получения GPU: {gpu_info['error']}"
            
            gpus = gpu_info.get("gpus", [])
            
            if not gpus:
                return False, "GPU не найдены"
            
            # Ищем Intel Iris Xe
            intel_iris_xe = None
            for gpu in gpus:
                if self.is_intel_iris_xe(gpu["name"]):
                    intel_iris_xe = gpu
                    break
            
            if not intel_iris_xe:
                return False, "Intel Iris Xe Graphics не найден"
            
            # Проверяем видеопамять
            vram_info = self.get_vram_usage()
            
            if "error" in vram_info:
                return False, f"Ошибка получения VRAM: {vram_info['error']}"
            
            free_gb = vram_info.get("free_gb", 0)
            
            if free_gb < 4.0:
                return False, f"Недостаточно видеопамяти: {free_gb}GB (требуется 4GB+)"
            
            return True, f"Intel Iris Xe готов к использованию ({free_gb}GB свободной VRAM)"
            
        except Exception as e:
            return False, f"Ошибка проверки GPU: {e}"

    def get_recommended_device(self) -> Dict:
        """Получение рекомендации по устройству для обработки"""
        can_use, message = self.can_use_gpu()
        
        if can_use:
            vram_info = self.get_vram_usage()
            return {
                "device": "gpu",
                "device_name": "Intel Iris Xe Graphics",
                "reason": message,
                "vram_info": vram_info,
                "performance": "high"
            }
        else:
            return {
                "device": "cpu",
                "device_name": "CPU",
                "reason": message,
                "performance": "medium"
            }

    def get_system_info(self) -> Dict:
        """Получение полной информации о системе"""
        try:
            gpu_info = self.get_gpu_info()
            vram_info = self.get_vram_usage()
            device_recommendation = self.get_recommended_device()
            
            # Информация о системе
            memory = psutil.virtual_memory()
            cpu_count = psutil.cpu_count()
            
            return {
                "system": {
                    "platform": platform.system(),
                    "cpu_cores": cpu_count,
                    "ram_total_gb": round(memory.total / (1024**3), 2),
                    "ram_available_gb": round(memory.available / (1024**3), 2)
                },
                "gpu": gpu_info,
                "vram": vram_info,
                "recommendation": device_recommendation
            }
            
        except Exception as e:
            return {"error": f"Ошибка получения информации о системе: {e}"}

def main():
    """Тестирование модуля"""
    print("GPU Manager - Тестирование (Fixed Version)")
    print("=" * 50)
    
    manager = GPUManager()
    
    # Получаем информацию о системе
    system_info = manager.get_system_info()
    
    if "error" in system_info:
        print(f"ERROR - {system_info['error']}")
        return
    
    # Выводим информацию о системе
    sys_info = system_info["system"]
    print(f"Платформа: {sys_info['platform']}")
    print(f"CPU ядер: {sys_info['cpu_cores']}")
    print(f"RAM: {sys_info['ram_total_gb']}GB (доступно: {sys_info['ram_available_gb']}GB)")
    print()
    
    # Выводим информацию о GPU
    gpu_info = system_info["gpu"]
    if "gpus" in gpu_info:
        print("Найденные GPU:")
        for i, gpu in enumerate(gpu_info["gpus"], 1):
            print(f"  {i}. {gpu['name']}")
            if gpu['ram']:
                try:
                    ram_mb = int(gpu['ram']) / (1024**2)
                    print(f"     Память: {ram_mb:.0f}MB")
                except:
                    print(f"     Память: {gpu['ram']}")
            if gpu['driver']:
                print(f"     Драйвер: {gpu['driver']}")
        print()
    elif "error" in gpu_info:
        print(f"Ошибка GPU: {gpu_info['error']}")
        print()
    
    # Выводим информацию о VRAM
    vram_info = system_info["vram"]
    if "error" not in vram_info:
        print("Видеопамять:")
        print(f"  Всего: {vram_info.get('total_mb', 0)}MB")
        print(f"  Используется: {vram_info.get('used_mb', 0)}MB")
        print(f"  Свободно: {vram_info.get('free_mb', 0)}MB ({vram_info.get('free_gb', 0)}GB)")
        if vram_info.get('estimated'):
            print(f"  (Оценка: {vram_info.get('note', '')})")
        print()
    else:
        print(f"Ошибка VRAM: {vram_info['error']}")
        print()
    
    # Выводим рекомендацию
    recommendation = system_info["recommendation"]
    print("Рекомендация:")
    print(f"  Device: {recommendation['device'].upper()}")
    print(f"  Название: {recommendation['device_name']}")
    print(f"  Причина: {recommendation['reason']}")
    print(f"  Производительность: {recommendation['performance']}")

if __name__ == "__main__":
    main()
