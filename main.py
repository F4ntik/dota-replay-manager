# Основной скрипт для запуска обработки реплея.

import argparse
# Старый парсер-заглушка больше не используется:
# from replay_parser import parse_replay_file 
from replay_reader import read_replay_file, ReplayParsingError, InvalidReplayFileError
from text_formatter import format_replay_to_text
from json_formatter import format_replay_to_json
# data_structures импортируется через другие модули, ReplayData будет доступен

def main():
    """
    Главная функция скрипта.

    Отвечает за парсинг аргументов командной строки, вызов парсера реплея,
    форматировщиков (в текстовый и JSON виды) и вывод результатов
    в указанные файлы или в консоль.
    """
    # Настройка парсера аргументов командной строки
    parser = argparse.ArgumentParser(description="Обработчик файлов реплеев Dota.")
    parser.add_argument("replay_file", help="Путь к файлу реплея (например, .w3g)")
    parser.add_argument(
        "--output-text",
        metavar="<file_path>",
        help="Путь к файлу для сохранения текстового вывода. Если не указан, вывод будет в консоль."
    )
    parser.add_argument(
        "--output-json",
        metavar="<file_path>",
        help="Путь к файлу для сохранения JSON вывода. Если не указан, вывод будет в консоль."
    )

    args = parser.parse_args()

    # Шаг 1: Парсинг файла реплея с использованием нового парсера
    print(f"Обработка файла реплея: {args.replay_file}")
    replay_data = None # Инициализируем replay_data как None
    try:
        print(f"DEBUG: Попытка прочитать файл: {args.replay_file}")
        replay_data = read_replay_file(args.replay_file)
    except FileNotFoundError:
        print(f"Ошибка: Файл реплея не найден по пути '{args.replay_file}'.")
        return # Выход из программы
    except InvalidReplayFileError as e:
        print(f"Ошибка: Файл '{args.replay_file}' не является корректным файлом реплея Warcraft III. {e}")
        return
    except ReplayParsingError as e:
        print(f"Ошибка при парсинге реплея '{args.replay_file}': {e}")
        return
    except Exception as e: # Перехват других неожиданных ошибок из парсера
        print(f"Неожиданная ошибка при обработке файла '{args.replay_file}': {e}")
        import traceback
        traceback.print_exc() # Для отладки выводим полный стектрейс
        return

    if replay_data is None:
        # Эта проверка может быть избыточной, если read_replay_file всегда выбрасывает исключение при ошибке,
        # но оставим для надежности, если read_replay_file вернет None без исключения.
        print(f"Не удалось получить данные из реплея '{args.replay_file}'. Парсер вернул None.")
        return
        
    print("Файл реплея успешно обработан парсером.")
    print("-" * 30)

    # Шаг 2: Форматирование в текстовый вид
    # Предполагается, что replay_data здесь уже не None
    text_output = format_replay_to_text(replay_data)

    # Шаг 3: Форматирование в JSON вид
    json_output = format_replay_to_json(replay_data)

    # Шаг 4: Обработка вывода текстовых данных
    if args.output_text:
        try:
            with open(args.output_text, "w", encoding="utf-8") as f:
                f.write(text_output)
            print(f"Текстовый вывод сохранен в: {args.output_text}")
        except IOError as e:
            print(f"Ошибка при записи текстового файла {args.output_text}: {e}")
            print("Текстовый вывод:")
            print(text_output)
    else:
        print("Текстовый вывод:")
        print(text_output)
    
    print("-" * 30)

    # Шаг 5: Обработка вывода JSON данных
    if args.output_json:
        try:
            with open(args.output_json, "w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"JSON вывод сохранен в: {args.output_json}")
        except IOError as e:
            print(f"Ошибка при записи JSON файла {args.output_json}: {e}")
            print("JSON вывод:")
            print(json_output)
    else:
        print("JSON вывод:")
        print(json_output)

if __name__ == "__main__":
    main()
