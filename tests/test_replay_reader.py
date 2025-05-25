import unittest
import os
import struct
import zlib
import io

# Предполагаем, что replay_reader и data_structures находятся в корне проекта
# и run_tests.py добавляет корень проекта в sys.path
from replay_reader import read_replay_file, ReplayParsingError, InvalidReplayFileError
from data_structures import ReplayData, GameInfo, PlayerInfo, PlayerStats, ItemBuildEntry, SkillBuildEntry

# Константы, необходимые для генерации тестового реплея (скопированы из replay_reader.py)
REPLAY_INTRO = b"Warcraft III recorded game\x1a\x00"
GAME_IDENTIFIER_W3XP = b"W3XP"
PLAYER_RECORD_ID = 0x16
TEAM_SENTINEL = 0x00
TEAM_SCOURGE = 0x01
SLOT_STATUS_OCCUPIED = 0x02
PLAYER_TYPE_HUMAN = 0x00
CHAT_MESSAGE_ID = 0x20 # Используется в примере
PLAYER_LEFT_ID = 0x22 # Используется в примере
# Добавим недостающие константы, на которые может ругаться код из __main__ replay_reader
GAME_IDENTIFIER_PX3W = b"PX3W" 
GAME_END_ID = 0x1D # Пример, точное значение не критично для структуры теста, но нужно для запуска кода из __main__
COMMAND_BLOCK_0x20 = 0x20 # Пример

# Путь к тестовому файлу реплея
# Тест будет создавать и удалять этот файл
TEST_REPLAY_FILENAME = "dummy_test_replay_for_unittest.w3g"

def generate_dummy_replay_file(filepath: str):
    # Эта функция адаптирована из секции if __name__ == '__main__' файла replay_reader.py
    # для генерации простого реплея для теста.
    try:
        # --- Заголовок (68 байт для версии 0x01) ---
        header_content = REPLAY_INTRO 
        header_content += struct.pack('<I', 68)    # header_size
        header_content += struct.pack('<I', 200)   # compressed_file_size (примерный)
        header_content += struct.pack('<I', 1)     # header_version (0x01)
        header_content += struct.pack('<I', 500)  # decompressed_file_size (общий)
        header_content += struct.pack('<I', 1)     # num_data_blocks
        header_content += GAME_IDENTIFIER_W3XP      # game_identifier
        header_content += struct.pack('<I', 26)    # game_version_patch_num (1.26)
        header_content += struct.pack('<H', 6060)  # build_number
        header_content += struct.pack('<H', 0x8000)# flags (single player)
        header_content += struct.pack('<I', 60000) # game_length_ms (1 минута)
        header_content += struct.pack('<I', 12345678) # CRC32 заголовка (заглушка)

        # --- Данные для блока ---
        decompressed_payload_stream = io.BytesIO()
        
        # SubHeader (минимальный)
        decompressed_payload_stream.write(b'\x00\x00\x00\x00\x00') # 5 нулей, как в replay_reader
        
        # Host PlayerRecord
        decompressed_payload_stream.write(bytes([PLAYER_RECORD_ID])) 
        decompressed_payload_stream.write(b'\x01') # Host Player ID (1)
        decompressed_payload_stream.write(b'PlayerHost\x00') 
        decompressed_payload_stream.write(b'\x01') # size_of_additional_data (1 байт)
        decompressed_payload_stream.write(b'\x00') # Custom game null byte
        
        decompressed_payload_stream.write(b'Test Game Name\x00') # GameName
        decompressed_payload_stream.write(b'\x00') # Null byte separator

        # EncodedString (очень упрощенная)
        # Map path, Creator name, settings_string (speed, visibility, etc.)
        # map_flags(1), w(2),h(2),crc(4), map_path(str), creator_name(str), settings_bytes(str)
        encoded_str_source_data = io.BytesIO()
        encoded_str_source_data.write(b'\x08') # map_flags
        encoded_str_source_data.write(struct.pack('<HH_I',128,128,0x1234))
        encoded_str_source_data.write(b'TestMap.w3x\x00')
        encoded_str_source_data.write(b'TestCreator\x00')
        settings_bytes = bytes([0x02,0x03,0x00,0x00,0x01,0x01,0x00,0x00,0x00]) + b'\xCC' 
        encoded_str_source_data.write(settings_bytes + b'\x00')
        
        raw_enc_str_bytes = encoded_str_source_data.getvalue()
        truly_encoded_for_decoder = bytearray()
        mask_test = 0
        for byte_val_test in raw_enc_str_bytes:
            byte_val_in_file_test = byte_val_test ^ mask_test
            truly_encoded_for_decoder.append(byte_val_in_file_test)
            if byte_val_in_file_test != 0:
                 mask_test = byte_val_test
        
        decompressed_payload_stream.write(bytes(truly_encoded_for_decoder))
        decompressed_payload_stream.write(b'\x00') # Terminator for Encoded String

        decompressed_payload_stream.write(struct.pack('<I', 1)) # PlayerCount (для PlayerList, не считая хоста)
        decompressed_payload_stream.write(b'DOTA') # GameType
        decompressed_payload_stream.write(b'enUS') # LanguageID

        # PlayerRecord для второго игрока
        decompressed_payload_stream.write(bytes([PLAYER_RECORD_ID, 0x02, *b'Player2\x00', 0x01, 0x00, 0x00, 0x00]))

        # SlotRecords
        decompressed_payload_stream.write(bytes([2])) # num_player_slots = 2
        # Slot 1: PlayerHost (ID 1, Sentinel, Blue)
        decompressed_payload_stream.write(bytes([0x01, 0x64, SLOT_STATUS_OCCUPIED, PLAYER_TYPE_HUMAN, TEAM_SENTINEL, 0x01, 0x01,0x00,0x64]))
        # Slot 2: Player2 (ID 2, Scourge, Red)
        decompressed_payload_stream.write(bytes([0x02, 0x64, SLOT_STATUS_OCCUPIED, PLAYER_TYPE_HUMAN, TEAM_SCOURGE, 0x00, 0x02,0x00,0x64]))

        decompressed_payload_stream.write(struct.pack('<I', 12345)) # RandomSeed
        decompressed_payload_stream.write(b'\x01') # SelectMode
        decompressed_payload_stream.write(b'\x00') # StartSpotCount
        
        # Простейший TimeSlot блок (пустой, только для структуры)
        decompressed_payload_stream.write(b'\x1F') # TimeSlot block ID
        decompressed_payload_stream.write(struct.pack('<HH', 0, 100)) # num_bytes_in_block=0, time_increment_ms=100

        # Завершающий блок (необязательно, но для полноты)
        # decompressed_payload_stream.write(bytes([GAME_END_ID]))
        # decompressed_payload_stream.write(struct.pack('<I',0)) # 4 байта причины конца игры

        decompressed_block_data_final = decompressed_payload_stream.getvalue()
        compressed_payload_test = zlib.compress(decompressed_block_data_final)
        
        # --- Информация о блоках данных (1 блок) ---
        # header_size (68) + block_info_size (8) + compressed_size должен быть равен total_file_size (200)
        # comp_block_size = 200 - 68 - 8 = 124
        comp_block_size_actual = len(compressed_payload_test)
        decomp_block_size_actual = len(decompressed_block_data_final)

        # Обновляем header_content с реальными размерами
        header_content = REPLAY_INTRO 
        header_content += struct.pack('<I', 68)    # header_size
        header_content += struct.pack('<I', 68 + 8 + comp_block_size_actual) # total_file_size
        header_content += struct.pack('<I', 1)     # header_version (0x01)
        header_content += struct.pack('<I', decomp_block_size_actual) # decompressed_file_size (общий)
        header_content += struct.pack('<I', 1)     # num_data_blocks
        header_content += GAME_IDENTIFIER_W3XP
        header_content += struct.pack('<I', 26) 
        header_content += struct.pack('<H', 6060)
        header_content += struct.pack('<H', 0x8000)
        header_content += struct.pack('<I', 60000)
        header_content += struct.pack('<I', 12345678)

        blocks_info_content = struct.pack('<HH_I', comp_block_size_actual, decomp_block_size_actual, 0) # crc заглушка

        with open(filepath, 'wb') as f_dummy:
            f_dummy.write(header_content)
            f_dummy.write(blocks_info_content)
            f_dummy.write(compressed_payload_test)
    except Exception as e:
        # Если генерация падает, тест должен это явно показать
        print(f"ОШИБКА ГЕНЕРАЦИИ ТЕСТОВОГО ФАЙЛА: {e}")
        raise

class TestReplayReader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Генерируем тестовый файл один раз для всех тестов в классе
        generate_dummy_replay_file(TEST_REPLAY_FILENAME)

    @classmethod
    def tearDownClass(cls):
        # Удаляем тестовый файл после всех тестов
        if os.path.exists(TEST_REPLAY_FILENAME):
            os.remove(TEST_REPLAY_FILENAME)

    def test_read_dummy_replay(self):
        # Тестируем чтение сгенерированного dummy-реплея
        replay_data = None
        try:
            replay_data = read_replay_file(TEST_REPLAY_FILENAME)
        except Exception as e:
            self.fail(f"read_replay_file возбудил исключение {type(e).__name__}: {e}")

        self.assertIsNotNone(replay_data, "ReplayData не должен быть None")
        self.assertIsInstance(replay_data, ReplayData, "Объект должен быть экземпляром ReplayData")
        
        # Проверки для GameInfo
        self.assertIsNotNone(replay_data.game_info, "GameInfo не должен быть None")
        self.assertEqual(replay_data.game_info.game_name, "Test Game Name")
        self.assertEqual(replay_data.game_info.map_name, "TestMap.w3x")
        self.assertEqual(replay_data.game_info.dota_version_str, "1.26") # Из заголовка
        self.assertEqual(replay_data.game_info.game_length_str, "00:01:00") # 60000 ms

        # Проверки для игроков
        self.assertIsNotNone(replay_data.detailed_player_reports, "Список игроков не должен быть None")
        self.assertEqual(len(replay_data.detailed_player_reports), 2, "Должно быть 2 игрока")

        player_host = next((p for p in replay_data.detailed_player_reports if p.player_id == 1), None)
        player2 = next((p for p in replay_data.detailed_player_reports if p.player_id == 2), None)

        self.assertIsNotNone(player_host, "Игрок-хост (ID 1) должен присутствовать")
        self.assertEqual(player_host.name, "PlayerHost")
        self.assertEqual(player_host.team_id, TEAM_SENTINEL) # 0

        self.assertIsNotNone(player2, "Игрок 2 (ID 2) должен присутствовать")
        self.assertEqual(player2.name, "Player2")
        self.assertEqual(player2.team_id, TEAM_SCOURGE) # 1
        
        # Проверка команд (после data_aggregator)
        # data_aggregator вызывается внутри read_replay_file
        self.assertEqual(len(replay_data.teams), 2)
        sentinel_team = next(t for t in replay_data.teams if t.name == "Sentinel")
        scourge_team = next(t for t in replay_data.teams if t.name == "Scourge")
        self.assertEqual(len(sentinel_team.lanes[0].players), 1)
        self.assertEqual(sentinel_team.lanes[0].players[0].name, "PlayerHost")
        self.assertEqual(len(scourge_team.lanes[0].players), 1)
        self.assertEqual(scourge_team.lanes[0].players[0].name, "Player2")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
