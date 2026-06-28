#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для GPU Manager
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Добавляем путь к проекту
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.gpu_manager import GPUManager


class TestGPUManager(unittest.TestCase):
    """Тесты для GPUManager"""
    
    def setUp(self):
        """Настройка тестов"""
        self.gpu_manager = GPUManager()
    
    def test_init(self):
        """Тест инициализации"""
        self.assertIsNotNone(self.gpu_manager)
        self.assertEqual(self.gpu_manager.system, "Windows")
        self.assertIsNone(self.gpu_manager.gpu_info)
        self.assertIsNone(self.gpu_manager.vram_info)
    
    def test_is_intel_iris_xe(self):
        """Тест проверки Intel Iris Xe"""
        # Положительные случаи
        self.assertTrue(self.gpu_manager.is_intel_iris_xe("Intel Iris Xe Graphics"))
        self.assertTrue(self.gpu_manager.is_intel_iris_xe("Intel(R) Iris(R) Xe Graphics"))
        self.assertTrue(self.gpu_manager.is_intel_iris_xe("INTEL IRIS XE GRAPHICS"))
        
        # Отрицательные случаи
        self.assertFalse(self.gpu_manager.is_intel_iris_xe("NVIDIA GeForce RTX 3060"))
        self.assertFalse(self.gpu_manager.is_intel_iris_xe("AMD Radeon RX 6600"))
        self.assertFalse(self.gpu_manager.is_intel_iris_xe("Intel HD Graphics 620"))
        self.assertFalse(self.gpu_manager.is_intel_iris_xe(""))
        self.assertFalse(self.gpu_manager.is_intel_iris_xe(None))
    
    @patch('subprocess.run')
    def test_get_windows_gpu_info_success(self, mock_run):
        """Тест успешного получения информации о GPU"""
        # Мокаем успешный ответ wmic
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """Node,Name,AdapterRAM,DriverVersion
DESKTOP-ABC123,Intel Iris Xe Graphics,2147483648,30.0.101.1404
DESKTOP-ABC123,NVIDIA GeForce RTX 3060,8589934592,471.96"""
        mock_run.return_value = mock_result
        
        result = self.gpu_manager._get_windows_gpu_info()
        
        self.assertIn("gpus", result)
        self.assertEqual(len(result["gpus"]), 2)
        self.assertEqual(result["gpus"][0]["name"], "Intel Iris Xe Graphics")
        self.assertEqual(result["gpus"][1]["name"], "NVIDIA GeForce RTX 3060")
    
    @patch('subprocess.run')
    def test_get_windows_gpu_info_error(self, mock_run):
        """Тест ошибки получения информации о GPU"""
        # Мокаем ошибку wmic
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        result = self.gpu_manager._get_windows_gpu_info()
        
        self.assertIn("error", result)
        self.assertIn("Не удалось получить информацию о GPU", result["error"])
    
    @patch('subprocess.run')
    def test_get_vram_usage_nvidia(self, mock_run):
        """Тест получения VRAM для NVIDIA"""
        # Мокаем nvidia-smi
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "8192, 2048, 6144"
        mock_run.return_value = mock_result
        
        result = self.gpu_manager.get_vram_usage()
        
        self.assertEqual(result["total_mb"], 8192)
        self.assertEqual(result["used_mb"], 2048)
        self.assertEqual(result["free_mb"], 6144)
        self.assertEqual(result["free_gb"], 6.0)
    
    @patch('subprocess.run')
    @patch('psutil.virtual_memory')
    def test_get_vram_usage_intel_fallback(self, mock_memory, mock_run):
        """Тест fallback для Intel GPU"""
        # Мокаем ошибку nvidia-smi
        mock_run.side_effect = FileNotFoundError()
        
        # Мокаем системную память
        mock_mem = MagicMock()
        mock_mem.total = 16 * 1024**3  # 16GB
        mock_memory.return_value = mock_mem
        
        result = self.gpu_manager._get_intel_vram_info()
        
        self.assertIn("total_mb", result)
        self.assertIn("free_mb", result)
        self.assertIn("estimated", result)
        self.assertTrue(result["estimated"])
    
    def test_can_use_gpu_no_gpu(self):
        """Тест когда GPU не найден"""
        with patch.object(self.gpu_manager, 'get_gpu_info') as mock_gpu_info:
            mock_gpu_info.return_value = {"gpus": []}
            
            can_use, message = self.gpu_manager.can_use_gpu()
            
            self.assertFalse(can_use)
            self.assertIn("GPU не найдены", message)
    
    def test_can_use_gpu_no_intel_iris_xe(self):
        """Тест когда Intel Iris Xe не найден"""
        with patch.object(self.gpu_manager, 'get_gpu_info') as mock_gpu_info:
            mock_gpu_info.return_value = {
                "gpus": [{"name": "NVIDIA GeForce RTX 3060", "ram": "8589934592", "driver": "471.96"}]
            }
            
            can_use, message = self.gpu_manager.can_use_gpu()
            
            self.assertFalse(can_use)
            self.assertIn("Intel Iris Xe Graphics не найден", message)
    
    def test_can_use_gpu_insufficient_vram(self):
        """Тест когда недостаточно видеопамяти"""
        with patch.object(self.gpu_manager, 'get_gpu_info') as mock_gpu_info, \
             patch.object(self.gpu_manager, 'get_vram_usage') as mock_vram:
            
            mock_gpu_info.return_value = {
                "gpus": [{"name": "Intel Iris Xe Graphics", "ram": "2147483648", "driver": "30.0.101.1404"}]
            }
            mock_vram.return_value = {"free_gb": 2.0}  # Меньше 4GB
            
            can_use, message = self.gpu_manager.can_use_gpu()
            
            self.assertFalse(can_use)
            self.assertIn("Недостаточно видеопамяти", message)
    
    def test_can_use_gpu_success(self):
        """Тест успешной проверки GPU"""
        with patch.object(self.gpu_manager, 'get_gpu_info') as mock_gpu_info, \
             patch.object(self.gpu_manager, 'get_vram_usage') as mock_vram:
            
            mock_gpu_info.return_value = {
                "gpus": [{"name": "Intel Iris Xe Graphics", "ram": "2147483648", "driver": "30.0.101.1404"}]
            }
            mock_vram.return_value = {"free_gb": 6.0}  # Больше 4GB
            
            can_use, message = self.gpu_manager.can_use_gpu()
            
            self.assertTrue(can_use)
            self.assertIn("Intel Iris Xe готов к использованию", message)
    
    def test_get_recommended_device_gpu(self):
        """Тест рекомендации GPU"""
        with patch.object(self.gpu_manager, 'can_use_gpu') as mock_can_use, \
             patch.object(self.gpu_manager, 'get_vram_usage') as mock_vram:
            
            mock_can_use.return_value = (True, "Intel Iris Xe готов")
            mock_vram.return_value = {"free_gb": 6.0}
            
            result = self.gpu_manager.get_recommended_device()
            
            self.assertEqual(result["device"], "gpu")
            self.assertEqual(result["device_name"], "Intel Iris Xe Graphics")
            self.assertEqual(result["performance"], "high")
    
    def test_get_recommended_device_cpu(self):
        """Тест рекомендации CPU"""
        with patch.object(self.gpu_manager, 'can_use_gpu') as mock_can_use:
            mock_can_use.return_value = (False, "GPU не найден")
            
            result = self.gpu_manager.get_recommended_device()
            
            self.assertEqual(result["device"], "cpu")
            self.assertEqual(result["device_name"], "CPU")
            self.assertEqual(result["performance"], "medium")
    
    @patch('psutil.virtual_memory')
    @patch('psutil.cpu_count')
    def test_get_system_info(self, mock_cpu_count, mock_memory):
        """Тест получения информации о системе"""
        mock_cpu_count.return_value = 8
        mock_mem = MagicMock()
        mock_mem.total = 16 * 1024**3  # 16GB
        mock_mem.available = 8 * 1024**3  # 8GB
        mock_memory.return_value = mock_mem
        
        with patch.object(self.gpu_manager, 'get_gpu_info') as mock_gpu_info, \
             patch.object(self.gpu_manager, 'get_vram_usage') as mock_vram, \
             patch.object(self.gpu_manager, 'get_recommended_device') as mock_device:
            
            mock_gpu_info.return_value = {"gpus": []}
            mock_vram.return_value = {"free_gb": 0}
            mock_device.return_value = {"device": "cpu", "device_name": "CPU"}
            
            result = self.gpu_manager.get_system_info()
            
            self.assertIn("system", result)
            self.assertIn("gpu", result)
            self.assertIn("vram", result)
            self.assertIn("recommendation", result)
            
            self.assertEqual(result["system"]["cpu_cores"], 8)
            self.assertEqual(result["system"]["ram_total_gb"], 16.0)


if __name__ == "__main__":
    unittest.main()
