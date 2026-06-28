#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для модуля скачивания модели Vosk
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Добавляем пути к модулям
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from utils.model_downloader import ModelDownloader, download_model_if_needed
from utils.config import Config


class TestModelDownloader(unittest.TestCase):
    """Тесты для класса ModelDownloader"""
    
    def setUp(self):
        """Настройка тестов"""
        self.config = Config()
        self.downloader = ModelDownloader(self.config)
    
    def test_model_downloader_initialization(self):
        """Тест инициализации загрузчика"""
        self.assertEqual(self.downloader.model_name, "vosk-model-ru-0.42")
        self.assertIn("vosk-model-ru-0.42.zip", self.downloader.model_url)
        self.assertEqual(self.downloader.models_dir.name, "models")
    
    def test_model_paths(self):
        """Тест путей к модели"""
        expected_model_path = self.downloader.models_dir / "vosk-model-ru-0.42"
        expected_zip_path = self.downloader.models_dir / "vosk-model-ru-0.42.zip"
        
        self.assertEqual(self.downloader.model_path, expected_model_path)
        self.assertEqual(self.downloader.zip_path, expected_zip_path)
    
    @patch('utils.model_downloader.Path.exists')
    def test_is_model_present_true(self, mock_exists):
        """Тест проверки наличия модели (модель есть)"""
        mock_exists.return_value = True
        
        result = self.downloader.is_model_present()
        
        self.assertTrue(result)
        mock_exists.assert_called_once()
    
    @patch('utils.model_downloader.Path.exists')
    def test_is_model_present_false(self, mock_exists):
        """Тест проверки наличия модели (модели нет)"""
        mock_exists.return_value = False
        
        result = self.downloader.is_model_present()
        
        self.assertFalse(result)
        mock_exists.assert_called_once()
    
    @patch('utils.model_downloader.Path.exists')
    def test_is_archive_present_true(self, mock_exists):
        """Тест проверки наличия архива (архив есть)"""
        mock_exists.return_value = True
        
        result = self.downloader.is_archive_present()
        
        self.assertTrue(result)
        mock_exists.assert_called_once()
    
    @patch('utils.model_downloader.Path.exists')
    def test_is_archive_present_false(self, mock_exists):
        """Тест проверки наличия архива (архива нет)"""
        mock_exists.return_value = False
        
        result = self.downloader.is_archive_present()
        
        self.assertFalse(result)
        mock_exists.assert_called_once()
    
    @patch('utils.model_downloader.urllib.request.urlretrieve')
    @patch('utils.model_downloader.zipfile.ZipFile')
    @patch('utils.model_downloader.Path.mkdir')
    @patch('utils.model_downloader.Path.unlink')
    @patch('utils.model_downloader.ModelDownloader.is_model_present')
    def test_download_model_success(self, mock_present, mock_unlink, mock_mkdir, 
                                   mock_zipfile, mock_urlretrieve):
        """Тест успешного скачивания модели"""
        # Настраиваем моки
        mock_present.return_value = True
        mock_zipfile.return_value.__enter__.return_value = MagicMock()
        
        result = self.downloader.download_model()
        
        self.assertTrue(result)
        mock_mkdir.assert_called_once_with(exist_ok=True)
        mock_urlretrieve.assert_called_once()
        mock_zipfile.assert_called_once()
        mock_unlink.assert_called_once()
    
    @patch('utils.model_downloader.urllib.request.urlretrieve')
    @patch('utils.model_downloader.Path.mkdir')
    def test_download_model_network_error(self, mock_mkdir, mock_urlretrieve):
        """Тест ошибки сети при скачивании"""
        import urllib.error
        mock_urlretrieve.side_effect = urllib.error.URLError("Network error")
        
        result = self.downloader.download_model()
        
        self.assertFalse(result)
        mock_mkdir.assert_called_once_with(exist_ok=True)
    
    @patch('utils.model_downloader.ModelDownloader.is_model_present')
    def test_get_model_info_no_model(self, mock_present):
        """Тест получения информации о модели (модели нет)"""
        mock_present.return_value = False
        
        result = self.downloader.get_model_info()
        
        self.assertIsNone(result)
    
    @patch('utils.model_downloader.ModelDownloader.is_model_present')
    @patch('utils.model_downloader.Path.rglob')
    def test_get_model_info_with_model(self, mock_rglob, mock_present):
        """Тест получения информации о модели (модель есть)"""
        mock_present.return_value = True
        
        # Мокаем файлы модели
        mock_file = MagicMock()
        mock_file.stat.return_value.st_size = 1024 * 1024  # 1MB
        mock_file.is_file.return_value = True
        mock_rglob.return_value = [mock_file]
        
        # Мокаем существование основных файлов
        with patch.object(self.downloader.model_path, '__truediv__') as mock_div:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_div.return_value = mock_path
            
            result = self.downloader.get_model_info()
        
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'vosk-model-ru-0.42')
        self.assertGreater(result['size_mb'], 0)
        self.assertTrue(result['complete'])
    
    @patch('utils.model_downloader.ModelDownloader.get_model_info')
    def test_validate_model_valid(self, mock_get_info):
        """Тест валидации модели (модель валидна)"""
        mock_get_info.return_value = {
            'name': 'vosk-model-ru-0.42',
            'size_mb': 50.0,
            'complete': True,
            'missing_files': []
        }
        
        result = self.downloader.validate_model()
        
        self.assertTrue(result)
    
    @patch('utils.model_downloader.ModelDownloader.get_model_info')
    def test_validate_model_invalid(self, mock_get_info):
        """Тест валидации модели (модель невалидна)"""
        mock_get_info.return_value = {
            'name': 'vosk-model-ru-0.42',
            'size_mb': 50.0,
            'complete': False,
            'missing_files': ['am/final.mdl']
        }
        
        result = self.downloader.validate_model()
        
        self.assertFalse(result)
    
    @patch('utils.model_downloader.Path.exists')
    @patch('utils.model_downloader.Path.unlink')
    def test_cleanup(self, mock_unlink, mock_exists):
        """Тест очистки временных файлов"""
        mock_exists.return_value = True
        
        self.downloader.cleanup()
        
        mock_unlink.assert_called_once()
    
    @patch('utils.model_downloader.zipfile.ZipFile')
    @patch('utils.model_downloader.Path.mkdir')
    @patch('utils.model_downloader.ModelDownloader.is_model_present')
    def test_extract_archive_success(self, mock_present, mock_mkdir, mock_zipfile):
        """Тест успешной распаковки архива"""
        mock_present.return_value = True
        mock_zipfile.return_value.__enter__.return_value = MagicMock()
        
        result = self.downloader.extract_archive()
        
        self.assertTrue(result)
        mock_mkdir.assert_called_once_with(exist_ok=True)
        mock_zipfile.assert_called_once()
    
    @patch('utils.model_downloader.zipfile.ZipFile')
    @patch('utils.model_downloader.Path.mkdir')
    def test_extract_archive_bad_zip(self, mock_mkdir, mock_zipfile):
        """Тест ошибки при распаковке поврежденного архива"""
        import zipfile
        mock_zipfile.side_effect = zipfile.BadZipFile("Bad zip file")
        
        result = self.downloader.extract_archive()
        
        self.assertFalse(result)
        mock_mkdir.assert_called_once_with(exist_ok=True)


class TestDownloadModelIfNeeded(unittest.TestCase):
    """Тесты для функции download_model_if_needed"""
    
    def setUp(self):
        """Настройка тестов"""
        self.config = Config()
    
    @patch('utils.model_downloader.ModelDownloader')
    def test_download_model_if_needed_model_exists(self, mock_downloader_class):
        """Тест когда модель уже существует"""
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.is_model_present.return_value = True
        mock_downloader.validate_model.return_value = True
        
        result = download_model_if_needed(self.config)
        
        self.assertTrue(result)
        mock_downloader.is_model_present.assert_called_once()
        mock_downloader.validate_model.assert_called_once()
        mock_downloader.download_model.assert_not_called()
    
    @patch('utils.model_downloader.ModelDownloader')
    def test_download_model_if_needed_archive_present(self, mock_downloader_class):
        """Тест когда есть архив модели"""
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.is_model_present.return_value = False
        mock_downloader.is_archive_present.return_value = True
        mock_downloader.extract_archive.return_value = True
        
        result = download_model_if_needed(self.config)
        
        self.assertTrue(result)
        mock_downloader.is_model_present.assert_called_once()
        mock_downloader.is_archive_present.assert_called_once()
        mock_downloader.extract_archive.assert_called_once()
        mock_downloader.download_model.assert_not_called()
    
    @patch('utils.model_downloader.ModelDownloader')
    def test_download_model_if_needed_model_missing(self, mock_downloader_class):
        """Тест когда модель отсутствует"""
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.is_model_present.return_value = False
        mock_downloader.is_archive_present.return_value = False
        mock_downloader.download_model.return_value = True
        
        result = download_model_if_needed(self.config)
        
        self.assertTrue(result)
        mock_downloader.is_model_present.assert_called_once()
        mock_downloader.is_archive_present.assert_called_once()
        mock_downloader.download_model.assert_called_once()
    
    @patch('utils.model_downloader.ModelDownloader')
    def test_download_model_if_needed_download_fails(self, mock_downloader_class):
        """Тест когда скачивание не удается"""
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.is_model_present.return_value = False
        mock_downloader.download_model.return_value = False
        
        result = download_model_if_needed(self.config)
        
        self.assertFalse(result)
        mock_downloader.is_model_present.assert_called_once()
        mock_downloader.download_model.assert_called_once()


def run_tests():
    """Запуск всех тестов"""
    print("🧪 Запуск тестов модуля скачивания модели...")
    
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем тесты
    suite.addTests(loader.loadTestsFromTestCase(TestModelDownloader))
    suite.addTests(loader.loadTestsFromTestCase(TestDownloadModelIfNeeded))
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Возвращаем результат
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
