# Этот скрипт предназначен для запуска всех тестов в проекте.
# Он автоматически обнаруживает и запускает все тестовые случаи,
# находящиеся в директории 'tests', и выводит результаты их выполнения.
# Также скрипт модифицирует PYTHONPATH для корректного импорта модулей проекта из тестов.

import unittest
import os

# Добавляем корневую директорию проекта в PYTHONPATH,
# чтобы можно было импортировать модули проекта (data_structures, text_formatter и т.д.)
# Это особенно важно, если тесты находятся во вложенной директории tests
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in os.sys.path: # Проверяем, чтобы не добавлять путь несколько раз, если скрипт запускается повторно
    os.sys.path.insert(0, project_root)

if __name__ == '__main__':
    # Комментарий: Этот скрипт предназначен для запуска всех тестов в проекте.
    
    # Загрузчик тестов
    loader = unittest.TestLoader()
    
    # Указываем директорию с тестами.
    # unittest.discover будет искать все файлы, соответствующие шаблону test_*.py
    # в указанной директории (в данном случае, 'tests').
    print(f"Ищем тесты в директории: {os.path.join(project_root, 'tests')}")
    suite = loader.discover('tests') 
    
    # Средство для запуска тестов
    # verbosity=2 для более детального вывода
    runner = unittest.TextTestRunner(verbosity=2)
    
    print("Запуск тестов...")
    result = runner.run(suite)

    # Вывод информации о результатах
    if result.wasSuccessful():
        print("Все тесты успешно пройдены.")
    else:
        print("Обнаружены ошибки в тестах.")
