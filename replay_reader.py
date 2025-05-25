# Этот модуль отвечает за чтение и парсинг файлов реплеев Warcraft III (.w3g).
# Реализовано чтение заголовка, декомпрессия блоков данных, парсинг суб-заголовка,
# чтение информации об игроках и обновление ее данными из записей слотов (команда, цвет),
# и пропуск метаданных до начала игровых действий.

import struct
import zlib
import io # Для работы с потоком байт
from typing import Optional, List, Tuple, Dict

from data_structures import (
    ReplayData, GameInfo, PlayerInfo, PlayerStats, ItemBuildEntry,
    SkillBuildEntry, TeamLane, TeamInfo, GameAction, ChatEntry
)

# Ожидаемое вступление в файле реплея
REPLAY_INTRO = b"Warcraft III recorded game\x1A\x00"
# Ожидаемый идентификатор игры для The Frozen Throne
GAME_IDENTIFIER_W3XP = b"W3XP"
GAME_IDENTIFIER_PX3W = b"PX3W"  # Альтернативный (байты в обратном порядке) идентификатор, встречающийся в некоторых реплеях DotA
# Идентификаторы блоков данных
PLAYER_RECORD_ID = 0x16        # Запись об игроке (имя, раса и т.д.)
# PLAYER_SLOT_RECORD_ID = 0x19 # Не ID блока, а структура после списка игроков.
GAME_START_COUNTDOWN_ID = 0x17 # Не используется активно для данных
CHAT_MESSAGE_ID = 0x20         # Используется для сообщений чата и не только
PLAYER_LEFT_ID = 0x22          # Игрок покинул игру
# ... другие ID блоков по мере необходимости

# Константы для PlayerSlotRecord.TeamID
TEAM_SENTINEL = 0x00
TEAM_SCOURGE = 0x01
TEAM_NEUTRAL_PASSIVE = 0x02 # Также может использоваться для наблюдателей в некоторых контекстах
TEAM_NEUTRAL_AGGRESSIVE = 0x03 
TEAM_OBSERVER = 0x0C # Явные наблюдатели

# Константы для PlayerSlotRecord.SlotStatus
SLOT_STATUS_EMPTY = 0x00
SLOT_STATUS_CLOSED = 0x01
SLOT_STATUS_OCCUPIED = 0x02

# Константы для PlayerSlotRecord.ComputerPlayerFlag
PLAYER_TYPE_HUMAN = 0x00
PLAYER_TYPE_COMPUTER = 0x01
PLAYER_TYPE_NEUTRAL = 0x02 # Для нейтральных юнитов, занимающих "слот"
PLAYER_TYPE_RESCUABLE = 0x03 # Для спасаемых юнитов

# Карта цветов игроков (индекс -> название)
# Индексы соответствуют значениям из поля Color в PlayerSlotRecord
PLAYER_COLORS = {
    0: "Красный",
    1: "Синий",
    2: "Бирюзовый", # Teal
    3: "Фиолетовый",
    4: "Желтый",
    5: "Оранжевый",
    6: "Зеленый",
    7: "Розовый",
    8: "Серый",
    9: "Голубой",   # Light Blue
    10: "Темно-зеленый",
    11: "Коричневый",
    # Остальные цвета (12-15) обычно для наблюдателей или не используются стандартно
}

class ReplayParsingError(Exception):
    """Базовый класс для ошибок парсинга реплея."""
    pass

class InvalidReplayFileError(ReplayParsingError):
    """Ошибка, если файл не является корректным файлом реплея Warcraft III."""
    pass

def _read_null_terminated_string(stream: io.BytesIO, encoding: str = 'utf-8') -> str:
    """Читает из потока строку, завершающуюся нулевым байтом."""
    result = bytearray()
    while True:
        byte = stream.read(1)
        if not byte or byte == b'\x00':
            break
        result.append(byte[0])
    return result.decode(encoding, errors='replace')

def _decode_encoded_string(encoded_bytes: bytes) -> Dict[str, any]:
    """
    Декодирует "Encoded String" из суб-заголовка реплея.
    Эта строка содержит информацию о карте, создателе, скорости игры, флагах и т.д.

    Алгоритм декодирования основан на описании из replay_format.txt:
    "The string is deobfuscated by xoring each byte with a mask.
    The mask is initially 0. If a byte is 0, the mask is unchanged.
    Otherwise, the mask becomes the deobfuscated byte."

    Args:
        encoded_bytes (bytes): Закодированная строка байт.

    Returns:
        Dict[str, any]: Словарь с извлеченными данными (map_name, creator_name, game_speed_str и т.д.).
    """
    decoded_data = bytearray()
    mask = 0
    for byte_val in encoded_bytes:
        deobfuscated_byte = byte_val ^ mask
        decoded_data.append(deobfuscated_byte)
        
        if byte_val == 0:
            pass  # Маска не меняется, если исходный байт был 0
        else:
            mask = deobfuscated_byte # Маска становится равной декодированному байту
            
    data = {}
    stream = io.BytesIO(decoded_data)
    
    try:
        # Согласно replay_format.txt (Game settings / map information):
        _map_flags = stream.read(1)[0] 
        # print(f"  Decoded Map Flags: {_map_flags:#02x}")

        # 2. Map width (ushort), 3. Map height (ushort), 4. Map CRC (uint)
        # Эти поля обычно не используются напрямую для отображения, пропускаем их.
        _ = stream.read(2)  # Map width
        _ = stream.read(2)  # Map height
        _ = stream.read(4)  # Map CRC

        # 5. Map path (string)
        data['map_name'] = _read_null_terminated_string(stream)
        # print(f"  Decoded Map Name: {data['map_name']}")

        # 6. Creator name (string)
        data['creator_name'] = _read_null_terminated_string(stream)
        # print(f"  Decoded Creator Name: {data['creator_name']}")
        
        # 7. "Encoded string" (внутри основной, уже декодированной строки).
        # Это последовательность байт, описывающая настройки игры.
        # replay_format.txt называет это "Encoded map data string"
        # qlog называет это "settings_string"
        # Длина этой строки не фиксирована, читаем до конца или до следующего явного разделителя,
        # если бы он был (но обычно его нет, это просто "остаток" основной декодированной строки).
        
        # ВАЖНО: replay_format.txt указывает, что после Creator Name идет "Encoded string".
        # Это означает, что settings_string_bytes ДОЛЖЕН быть прочитан как null-terminated строка.
        settings_string_bytes = _read_null_terminated_string(stream, encoding='latin-1').encode('latin-1')
        # print(f"  Decoded Settings String (raw bytes, len {len(settings_string_bytes)}): {settings_string_bytes.hex()}")

        # Парсинг settings_string_bytes согласно структуре из replay_format.txt (Game settings byte flags)
        # или qlog/src/replay.cpp (load_game_data, после чтения settings_string)
        if settings_string_bytes: # Если строка не пустая
            # speed(1), visibility(1), flags(1), placement(1), teams_together(1), locked_teams(1), shared_control(1), random_hero(1), random_races(1), checksum(1)
            # Это как минимум 10 байт.
            
            # Game Speed
            game_speed_val = settings_string_bytes[0]
            if game_speed_val == 0x00: data['game_speed_str'] = "Slow"
            elif game_speed_val == 0x01: data['game_speed_str'] = "Normal"
            elif game_speed_val == 0x02: data['game_speed_str'] = "Fast"
            else: data['game_speed_str'] = f"Unknown ({game_speed_val:#02x})"
            # print(f"    Game Speed: {data['game_speed_str']}")

            if len(settings_string_bytes) > 1:
                # Visibility, Flags, etc.
                # visibility: 00=hide terrain, 01=explored, 02=always visible, 03=default
                visibility_val = settings_string_bytes[1]
                if visibility_val == 0x00: data['visibility_str'] = "Hide Terrain"
                elif visibility_val == 0x01: data['visibility_str'] = "Explored"
                elif visibility_val == 0x02: data['visibility_str'] = "Always Visible"
                elif visibility_val == 0x03: data['visibility_str'] = "Default"
                else: data['visibility_str'] = f"Unknown ({visibility_val:#02x})"
                # print(f"    Visibility: {data['visibility_str']}")
            
            # TODO: Детальный парсинг остальных флагов для game_mode_code_str
            # game_options (битовая маска из settings_string_bytes[2])
            # 0x01: teams fixed (locked teams)
            # 0x02: unused
            # 0x04: full shared unit control
            # 0x08: random hero
            # 0x10: random races
            # 0x20: unused
            # 0x40: cheats enabled
            # 0x80: observers allowed (?)
            #
            # game_placement (settings_string_bytes[3])
            # 0x00: fixed (teams are whatever was chosen in lobby)
            # 0x01: random (teams are random)
            # 0x02: fixed teams, random placement
            #
            # Для Dota, game_mode_code_str (например, -apshomdenp) формируется на основе этих флагов
            # и настроек карты. Это сложный парсинг, выходящий за рамки текущей задачи.
            data['game_mode_code_str'] = "Не извлечено (детально)" # Заглушка

    except Exception as e: # IndexError если строка короче, или другие ошибки
        print(f"Ошибка при парсинге содержимого декодированной строки: {e}")
        # Возвращаем то, что успели собрать
    return data

def get_player_color_name(color_byte: int) -> str:
    """Преобразует байт цвета игрока в строковое представление."""
    return PLAYER_COLORS.get(color_byte, f"Неизвестный цвет ({color_byte:#02x})")

def format_ms_to_hhmmss(milliseconds: int) -> str:
    """Конвертирует миллисекунды в строку формата HH:MM:SS."""
    seconds_total = milliseconds // 1000
    hours = seconds_total // 3600
    minutes = (seconds_total % 3600) // 60
    seconds = seconds_total % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def _parse_object_id(stream: io.BytesIO) -> str:
    """Читает 4 байта и возвращает их как строку ID (например, 'hfoo')."""
    obj_id_bytes = stream.read(4)
    if len(obj_id_bytes) < 4: raise ReplayParsingError("Не удалось прочитать Object ID (ожидалось 4 байта).")
    # ID предметов/юнитов/способностей могут быть нечитаемыми в utf-8, поэтому hex или latin-1
    try:
        return obj_id_bytes.decode('ascii')[::-1] # ID часто хранятся в обратном порядке байт
    except UnicodeDecodeError:
        return obj_id_bytes.hex() # Если не ASCII, возвращаем hex

def read_replay_file(filepath: str) -> Optional[ReplayData]:
    """
    Читает файл реплея Warcraft III (.w3g), парсит заголовок, суб-заголовок,
    информацию об игроках и слотах, и пропускает метаданные до начала игровых действий.

    Args:
        filepath (str): Путь к файлу реплея.

    Returns:
        Optional[ReplayData]: Объект ReplayData с заполненной информацией
                              или None в случае ошибки.
    """
    try:
        with open(filepath, 'rb') as f:
            # --- 1. Чтение и проверка вступления ---
            intro = f.read(len(REPLAY_INTRO))
            if intro != REPLAY_INTRO:
                raise InvalidReplayFileError("Файл не является реплеем Warcraft III (неверное вступление).")

            # --- 2. Чтение заголовка реплея ---
            header_size = struct.unpack('<I', f.read(4))[0]
            _ = struct.unpack('<I', f.read(4))[0] # compressed_file_size (не используется напрямую)
            header_version = struct.unpack('<I', f.read(4))[0]
            if header_version not in [0x00, 0x01]:
                 print(f"Предупреждение: Неожиданная версия заголовка: {header_version} (ожидались 0 или 1).")
            _ = struct.unpack('<I', f.read(4))[0] # decompressed_file_size (общий)
            num_data_blocks = struct.unpack('<I', f.read(4))[0]
            
            game_identifier = f.read(4)
            print(f"DEBUG: Прочитан идентификатор игры: {game_identifier} ({game_identifier.decode('ascii', errors='ignore')})")
            if game_identifier not in [GAME_IDENTIFIER_W3XP, GAME_IDENTIFIER_PX3W]:
                raise InvalidReplayFileError(f"Неверный идентификатор игры: {game_identifier.decode('ascii', errors='ignore')}. Ожидались W3XP или PX3W.")
            
            game_version_raw_bytes = f.read(4)
            game_version_patch_num = game_version_raw_bytes[0] 
            game_version_str = f"1.{game_version_patch_num}"
            
            _ = struct.unpack('<H', f.read(2))[0] # build_number
            _ = struct.unpack('<H', f.read(2))[0] # flags
            
            game_length_ms_bytes = f.read(4)
            if len(game_length_ms_bytes) < 4: raise ReplayParsingError("Не удалось прочитать длительность игры.")
            game_length_ms = struct.unpack('<I', game_length_ms_bytes)[0]

            if header_version == 0x01 and header_size != 68:
                 print(f"Предупреждение: header_size ({header_size}) не равен 68 для header_version 0x01 (влияет на CRC).")
            elif header_version == 0x00 and header_size != 40: # Для старых версий (до 1.07)
                 print(f"Предупреждение: header_size ({header_size}) не равен 40 для header_version 0x00 (влияет на CRC).")
            _ = f.read(4) # Пропускаем CRC32 заголовка

            # --- 3. Инициализация GameInfo (многие поля будут обновлены из суб-заголовка) ---
            game_info = GameInfo(
                date_time_str="Не определено", 
                game_mode_code_str="Не определено",
                game_length_str=format_ms_to_hhmmss(game_length_ms),
                player_ratio_str="Не определено", 
                game_score_str="Не определено", 
                winner_str="Не определено", 
                game_duration_seconds=game_length_ms // 1000,
                dota_version_str=game_version_str,
                map_name="Не определено", 
                game_name="Не определено", 
                game_speed_str = "Не определено"
            )

            # --- 4. Чтение и декомпрессия блоков данных ---
            decompressed_data_stream = io.BytesIO()
            for i in range(num_data_blocks):
                comp_size, decomp_size = struct.unpack('<HH', f.read(4))
                _ = f.read(4) # block_checksum

                if comp_size == 0:
                    if decomp_size > 0: # comp_size is 0, but expected decompressed size is not.
                        print(f"Предупреждение: Блок {i+1}: comp_size=0, но decomp_size={decomp_size}. Блок будет обработан как пустой.")
                    # If comp_size is 0 and decomp_size is 0, it's a truly empty block.
                    # In either case (comp_size=0, decomp_size=0 OR comp_size=0, decomp_size>0), we write no data.
                    continue
                
                compressed_block_data = f.read(comp_size)
                if len(compressed_block_data) < comp_size:
                    raise ReplayParsingError(f"Блок {i+1}: недочитаны данные (ожидалось {comp_size}, прочитано {len(compressed_block_data)}).")

                if i == 0: # Log for the first block
                    print(f"DEBUG: Блок 1 (comp_size={comp_size}, decomp_size={decomp_size}) - первые 32 байта compressed_block_data: {compressed_block_data[:32].hex()}")

                block_data_to_write = b''
                if comp_size == decomp_size: # Data is not compressed
                    block_data_to_write = compressed_block_data
                    # print(f"DEBUG: Блок {i+1}: данные не сжаты (comp_size == decomp_size == {comp_size}). Копируем как есть.")
                else: # Data is compressed (comp_size != decomp_size)
                    # print(f"DEBUG: Блок {i+1}: попытка декомпрессии (comp_size={comp_size}, decomp_size={decomp_size}).")
                    try:
                        block_data_to_write = zlib.decompress(compressed_block_data)
                    except zlib.error as e:
                        error_message_prefix = f"Блок {i+1}"
                        if header_version != 0x01: # Add header version info if it's an old replay
                            error_message_prefix += f" (заголовок вер. {header_version:#02x})"
                        raise ReplayParsingError(
                            f"{error_message_prefix}: ошибка zlib.decompress: {e} (comp_size={comp_size}, decomp_size={decomp_size}, read_data_len={len(compressed_block_data)})"
                        )
                
                # Validate size after decompression or copying
                if len(block_data_to_write) != decomp_size:
                     print(f"Предупреждение: Блок {i+1}: размер после обработки ({len(block_data_to_write)}) не совпадает с ожидаемым ({decomp_size}).")

                decompressed_data_stream.write(block_data_to_write)
            
            decompressed_data_stream.seek(0)

            # --- 5. Парсинг суб-заголовка (Replay Data Header) ---
            # Согласно w3g_format.txt v1.3 (by The Smerge), section 4.0
            # 4.1. The first 4 bytes of this section are 0. (The Smerge: "Actually, it's 5 bytes of 0")
            # Let's follow The Smerge's note and common parser implementations.
            skipped_initial_bytes = decompressed_data_stream.read(5)
            # print(f"DEBUG: Skipped initial 5 bytes of sub-header: {skipped_initial_bytes.hex()}")

            # 4.2. Host PlayerRecord (The Smerge: "This PlayerRecord is for the host.")
            # Initialize host player variables
            _host_player_id_val = -1
            _host_player_name_val = "Unknown Host"

            host_record_id_byte = decompressed_data_stream.read(1)
            if not host_record_id_byte:
                raise ReplayParsingError("Не удалось прочитать RecordID для хоста в суб-заголовке.")
            if host_record_id_byte[0] != PLAYER_RECORD_ID:
                raise ReplayParsingError(f"Ожидался PlayerRecordID (0x{PLAYER_RECORD_ID:02x}) для хоста в суб-заголовке, но получен 0x{host_record_id_byte[0]:02x}.")
            
            _host_player_id_val = decompressed_data_stream.read(1)[0]
            _host_player_name_val = _read_null_terminated_string(decompressed_data_stream)
            
            size_of_additional_data_byte = decompressed_data_stream.read(1)
            if not size_of_additional_data_byte:
                 raise ReplayParsingError("Не удалось прочитать size_of_additional_data для хоста.")
            size_of_additional_data = size_of_additional_data_byte[0]

            if size_of_additional_data == 0x01:
                _ = decompressed_data_stream.read(1) # Custom game null byte
            elif size_of_additional_data == 0x08:
                _ = decompressed_data_stream.read(8) # Ladder game runtime & race flags
            elif size_of_additional_data == 0x00: # Some replays might have 0 here.
                pass # No additional data to read
            else:
                print(f"Предупреждение: Неожиданный size_of_additional_data ({size_of_additional_data:#02x}) для хоста. Попытка пропустить {size_of_additional_data} байт.")
                _ = decompressed_data_stream.read(size_of_additional_data)
            
            # print(f"DEBUG: Host Player: ID={_host_player_id_val}, Name='{_host_player_name_val}'")

            # 4.3. GameName (null-terminated string)
            game_info.game_name = _read_null_terminated_string(decompressed_data_stream)
            # print(f"DEBUG: Game Name: {game_info.game_name}")

            # 4.4. Null byte separator
            _ = decompressed_data_stream.read(1) 

            # 4.5. EncodedString (null-terminated string)
            encoded_string_bytes = _read_null_terminated_string(decompressed_data_stream, encoding='latin-1').encode('latin-1')
            decoded_info_from_string = _decode_encoded_string(encoded_string_bytes)
            
            game_info.map_name = decoded_info_from_string.get('map_name', game_info.map_name)
            game_info.game_speed_str = decoded_info_from_string.get('game_speed_str', game_info.game_speed_str)
            game_info.game_mode_code_str = decoded_info_from_string.get('game_mode_code_str', game_info.game_mode_code_str)
            # print(f"DEBUG: Decoded Map: {game_info.map_name}, Speed: {game_info.game_speed_str}")

            # 4.6. PlayerCount (4 bytes, little-endian integer)
            # This is the count of players in the PlayerList that follows, not total slots.
            # The C++ code refers to this as 'slots', which might be confusing.
            # It's the number of PlayerRecord entries that will follow (excluding the host already parsed).
            _num_players_in_header_val_bytes = decompressed_data_stream.read(4)
            if len(_num_players_in_header_val_bytes) < 4:
                raise ReplayParsingError("Не удалось прочитать PlayerCount из суб-заголовка.")
            _num_players_in_header_val = struct.unpack('<I', _num_players_in_header_val_bytes)[0]
            # print(f"DEBUG: PlayerCount (from sub-header, for PlayerList): {_num_players_in_header_val}")
            
            # 4.7. GameType (4 bytes, typically an ID string like 'DOTA')
            _game_type_bytes = decompressed_data_stream.read(4)
            if len(_game_type_bytes) < 4: raise ReplayParsingError("Не удалось прочитать GameType.")
            # game_type_str = _game_type_bytes.decode('ascii', errors='ignore')
            # print(f"DEBUG: GameType Bytes: {_game_type_bytes.hex()} ({game_type_str})")

            # 4.8. LanguageID (4 bytes, e.g., 'enUS')
            _language_id_bytes = decompressed_data_stream.read(4)
            if len(_language_id_bytes) < 4: raise ReplayParsingError("Не удалось прочитать LanguageID.")
            # language_id_str = _language_id_bytes.decode('ascii', errors='ignore')
            # print(f"DEBUG: LanguageID Bytes: {_language_id_bytes.hex()} ({language_id_str})")


            # --- 6. Чтение информации об игроках (Player Records) ---
            # Section 4.9: PlayerList. This is a list of PlayerRecords.
            # The host PlayerRecord has already been parsed. This loop will parse the remaining players.
            players_map: Dict[int, PlayerInfo] = {}
            # Create PlayerInfo for the host, it will be updated later by slot records if present.
            # If the host is also in the slot records, their info (team, color) will be updated.
            # If not (e.g. only an observer), they will still be in players_map.
            if _host_player_id_val != -1: # Check if host was successfully parsed
                 players_map[_host_player_id_val] = PlayerInfo(
                        player_id=_host_player_id_val, name=_host_player_name_val, 
                        team_id=-1, color_str="Неизвестный", # Initial placeholders
                        hero_name="Не выбран", hero_id_str="", level=1,
                        stats=PlayerStats(0,0,0,0,0,0), gold=0, apm=0,
                        items_inventory=[], skill_build=[], item_build_timeline=[]
                    )
            # print("\nЧтение информации об игроках (Player Records):")
            while True:
                record_id_byte = decompressed_data_stream.read(1)
                if not record_id_byte: break 
                record_id = record_id_byte[0]

                if record_id == PLAYER_RECORD_ID:
                    p_id = decompressed_data_stream.read(1)[0]
                    p_name = _read_null_terminated_string(decompressed_data_stream)
                    _ = decompressed_data_stream.read(1) # Custom game flag / additional data
                    _ = decompressed_data_stream.read(1) # Race flag
                    _ = decompressed_data_stream.read(1) # AI strength
                    _ = decompressed_data_stream.read(1) # Handicap
                    
                    # print(f"  Прочитан PlayerRecord: ID={p_id}, Имя='{p_name}'")
                    players_map[p_id] = PlayerInfo(
                        player_id=p_id, name=p_name, team_id=-1, color_str="Неизвестный", # Заглушки
                        hero_name="Не выбран", hero_id_str="", level=1,
                        stats=PlayerStats(0,0,0,0,0,0), gold=0, apm=0, # Будут обновлены
                        items_inventory=[], skill_build=[], item_build_timeline=[]
                    )
                else:
                    decompressed_data_stream.seek(-1, io.SEEK_CUR) # Вернуть байт обратно
                    # print(f"Завершено чтение Player Records, следующий блок: {record_id:#02x}")
                    break
            
            # --- 7. Чтение информации о слотах игроков (Player Slot Records) ---
            # print("\nЧтение информации о слотах игроков (Player Slot Records):")
            num_player_slots_byte = decompressed_data_stream.read(1)
            if not num_player_slots_byte: raise ReplayParsingError("Не удалось прочитать количество слотов игроков.")
            num_player_slots = num_player_slots_byte[0]
            # print(f"  Количество слотов: {num_player_slots}")

            for i in range(num_player_slots):
                slot_data_bytes = decompressed_data_stream.read(9) # Каждый слот - 9 байт
                if len(slot_data_bytes) < 9:
                    raise ReplayParsingError(f"Не удалось прочитать полные данные для слота {i+1} (прочитано {len(slot_data_bytes)} байт).")

                slot_player_id = slot_data_bytes[0]
                _ = slot_data_bytes[1] # map_download_percent
                slot_status = slot_data_bytes[2]
                computer_player_flag = slot_data_bytes[3]
                slot_team_id = slot_data_bytes[4]
                slot_color_byte = slot_data_bytes[5]
                _player_race_flag_in_slot = slot_data_bytes[6] # Раса в слоте
                _ai_strength_in_slot = slot_data_bytes[7]
                _handicap_in_slot = slot_data_bytes[8]
                
                # print(f"  Слот {i}: PlayerID={slot_player_id}, TeamID={slot_team_id}, Color={slot_color_byte}, Status={slot_status}, Computer={computer_player_flag}")

                if slot_player_id == 0 and slot_status == SLOT_STATUS_EMPTY:
                    # Пустой слот, пропускаем
                    continue

                player_to_update = players_map.get(slot_player_id)

                if player_to_update: 
                    player_to_update.team_id = slot_team_id
                    player_to_update.color_str = get_player_color_name(slot_color_byte)
                    
                    # Обновляем имя, если это компьютер и имя еще не содержит "(Компьютер)"
                    # (может быть полезно, если PlayerRecord не всегда указывает на AI)
                    if computer_player_flag == PLAYER_TYPE_COMPUTER and "(Компьютер)" not in player_to_update.name:
                        player_to_update.name += " (Компьютер)"
                    elif computer_player_flag == PLAYER_TYPE_HUMAN and player_to_update.name.endswith(" (Компьютер)"):
                        # На случай, если ранее ошибочно добавили, а слот говорит, что человек
                        player_to_update.name = player_to_update.name.replace(" (Компьютер)", "").strip()
                        
                elif slot_status == SLOT_STATUS_OCCUPIED and computer_player_flag == PLAYER_TYPE_COMPUTER:
                    # Это компьютерный игрок, которого не было в PlayerRecord (например, "Computer (Easy)" в старых реплеях Dota)
                    # или если PlayerID = 0, но слот занят компьютером.
                    # Создаем для него PlayerInfo, если его еще нет.
                    # Если slot_player_id == 0, нужно сгенерировать уникальный ID, например, отрицательный.
                    # Но обычно у ИИ есть свой PlayerID > 0.
                    actual_slot_player_id_for_ai = slot_player_id
                    if actual_slot_player_id_for_ai == 0: # Очень редкий случай для ИИ, но возможный
                        # Генерируем временный уникальный ID для такого ИИ, чтобы не конфликтовать.
                        # Например, начиная с 200, или другой диапазон, не пересекающийся с реальными PlayerID.
                        actual_slot_player_id_for_ai = 200 + i 
                    
                    if actual_slot_player_id_for_ai not in players_map:
                        comp_player_name = f"Компьютер {actual_slot_player_id_for_ai}" 
                        # print(f"    Создание ИИ игрока из слота {i}: ID={actual_slot_player_id_for_ai}, Team={slot_team_id}, Color={slot_color_byte}")
                        players_map[actual_slot_player_id_for_ai] = PlayerInfo(
                            player_id=actual_slot_player_id_for_ai, name=comp_player_name, team_id=slot_team_id,
                            color_str=get_player_color_name(slot_color_byte),
                            hero_name="Не выбран", hero_id_str="", level=1,
                            stats=PlayerStats(0,0,0,0,0,0), gold=0, apm=0,
                            items_inventory=[], skill_build=[], item_build_timeline=[]
                        )
            
            # Обновляем player_ratio_str в GameInfo
            sentinel_count = sum(1 for p in players_map.values() if p.team_id == TEAM_SENTINEL and p.name and "(Компьютер)" not in p.name and p.name.lower() != "open" and p.name.lower() != "closed")
            scourge_count = sum(1 for p in players_map.values() if p.team_id == TEAM_SCOURGE and p.name and "(Компьютер)" not in p.name and p.name.lower() != "open" and p.name.lower() != "closed")
            
            if sentinel_count > 0 or scourge_count > 0:
                 game_info.player_ratio_str = f"{sentinel_count}v{scourge_count}"
            else:
                 active_players_count = sum(1 for p in players_map.values() if p.team_id not in [TEAM_OBSERVER, TEAM_NEUTRAL_PASSIVE, TEAM_NEUTRAL_AGGRESSIVE] and p.name and "(Компьютер)" not in p.name and p.name.lower() != "open" and p.name.lower() != "closed" )
                 game_info.player_ratio_str = f"{active_players_count} игроков"


            # --- 8. Пропуск оставшихся блоков до игровых действий ---
            # replay_format.txt: после слотов идет Random seed (uint32), Select Mode (byte), Start spot count (byte)
            
            _random_seed_bytes = decompressed_data_stream.read(4)
            if len(_random_seed_bytes) < 4: raise ReplayParsingError("Не удалось прочитать Random seed.")
            # random_seed = struct.unpack('<I', _random_seed_bytes)[0]
            # print(f"\nRandom Seed: {random_seed} ({_random_seed_bytes.hex()})")
            
            _select_mode_byte = decompressed_data_stream.read(1)
            if not _select_mode_byte: raise ReplayParsingError("Не удалось прочитать Select Mode.")
            # select_mode = _select_mode_byte[0] # 0x01=Fixed, 0x03=Random, 0x04=Manual
            # print(f"Select Mode: {select_mode:#02x}")
            
            _start_spot_count_byte = decompressed_data_stream.read(1)
            if not _start_spot_count_byte: raise ReplayParsingError("Не удалось прочитать Start spot count.")
            start_spot_count = _start_spot_count_byte[0]
            # print(f"Start Spot Count: {start_spot_count}")
            
            # Пропускаем сами стартовые позиции, если они есть.
            # В replay_format.txt не указано, что они здесь, но qlog их пропускает.
            # Каждая стартовая позиция это X (float) и Y (float) - итого 8 байт.
            # Это не всегда присутствует. Для Dota реплеев это обычно 0.
            if start_spot_count > 0:
                bytes_to_skip = start_spot_count * 8
                skipped_bytes = decompressed_data_stream.read(bytes_to_skip)
                if len(skipped_bytes) < bytes_to_skip:
                    raise ReplayParsingError(f"Не удалось пропустить все байты стартовых позиций (ожидалось {bytes_to_skip}, прочитано {len(skipped_bytes)}).")
                # print(f"Пропущено {len(skipped_bytes)} байт стартовых позиций.")

            # --- 9. Парсинг игровых действий ---
            game_actions_list: List[GameAction] = []
            chat_log_list: List[ChatEntry] = []
            current_time_ms = 0
            player_actions_count: Dict[int, int] = {pid: 0 for pid in players_map.keys()}


            while True:
                block_id_byte = decompressed_data_stream.read(1)
                if not block_id_byte: break # Конец потока
                block_id = block_id_byte[0]

                if block_id in [0x1E, 0x1F]: # TIMESLOT_BLOCK_0x1E_PRE_131, TIMESLOT_BLOCK_0x1F_POST_131
                    num_bytes_in_block, time_increment_ms = struct.unpack('<HH', decompressed_data_stream.read(4))
                    current_time_ms += time_increment_ms
                    
                    commands_data_read = decompressed_data_stream.read(num_bytes_in_block)
                    if len(commands_data_read) < num_bytes_in_block: raise ReplayParsingError("Неполные данные команд в TimeSlot блоке.")
                    
                    cmd_stream = io.BytesIO(commands_data_read)
                    while cmd_stream.tell() < num_bytes_in_block:
                        cmd_player_id = cmd_stream.read(1)[0]
                        cmd_data_len = struct.unpack('<H', cmd_stream.read(2))[0]
                        action_data_bytes = cmd_stream.read(cmd_data_len)
                        if len(action_data_bytes) < cmd_data_len: raise ReplayParsingError("Неполные данные для Action.")
                        
                        player_actions_count[cmd_player_id] = player_actions_count.get(cmd_player_id, 0) + 1
                        
                        action_stream = io.BytesIO(action_data_bytes)
                        # В одном блоке action_data_bytes может быть несколько ActionID подряд
                        while action_stream.tell() < cmd_data_len:
                            action_id_raw = action_stream.read(1)[0]
                            action_params: Dict[str, Any] = {}
                            action_type_str = f"UnknownAction_{action_id_raw:#02x}"
                            
                            # Здесь парсинг конкретных ActionID, как было в предыдущем полном коде
                            if action_id_raw == 0x10: # ACTION_SELECT_UNIT_GROUP (UseAbility/Build)
                                action_type_str = "UseAbilityBuild"
                                action_params['select_mode'] = action_stream.read(1)[0]
                                action_params['group_number'] = action_stream.read(1)[0]
                                object_id_str = _parse_object_id(action_stream)
                                if object_id_str.startswith('A'):
                                    action_params['ability_id'] = object_id_str
                                    action_params['item_id'] = None
                                else:
                                    action_params['item_id'] = object_id_str
                                    action_params['ability_id'] = None
                                action_params['ability_item_id2'] = _parse_object_id(action_stream) # This is likely flags or secondary ID
                            elif action_id_raw == 0x11: # ACTION_ASSIGN_GROUP_HOTKEY
                                action_type_str = "AssignGroupHotkey"
                                action_params['group_number'] = action_stream.read(1)[0]
                                num_selected = struct.unpack('<H', action_stream.read(2))[0]
                                action_stream.read(num_selected * 8) 
                            elif action_id_raw == 0x12: # ACTION_SELECT_GROUP_HOTKEY
                                action_type_str = "SelectGroupHotkey"
                                action_params['group_number'] = action_stream.read(1)[0]
                                _ = action_stream.read(1) 
                            elif action_id_raw == 0x13: # ACTION_SELECT_SUBGROUP
                                action_type_str = "SelectSubgroup"
                                action_params['subgroup_id'] = action_stream.read(1)[0]
                                _ = action_stream.read(4); _ = action_stream.read(4)
                            elif action_id_raw == 0x16: # ACTION_CHANGE_SELECTION
                                action_type_str = "ChangeSelection"
                                action_params['select_mode'] = action_stream.read(1)[0]
                                num_units = struct.unpack('<H', action_stream.read(2))[0]
                                action_stream.read(num_units * 8)
                            elif action_id_raw == 0x17: # ACTION_UNIT_ORDER_POINT
                                action_type_str = "UnitOrderPoint"
                                action_params['order_id'] = action_stream.read(1)[0]
                                _ = action_stream.read(2) 
                                action_params['pos_x'] = struct.unpack('<i', action_stream.read(4))[0]
                                action_params['pos_y'] = struct.unpack('<i', action_stream.read(4))[0]
                                action_stream.read(12) 
                            elif action_id_raw == 0x18: # ACTION_UNIT_ORDER_TARGET
                                action_type_str = "UnitOrderTarget"
                                action_params['order_id'] = action_stream.read(1)[0]
                                _ = action_stream.read(2) 
                                action_params['pos_x'] = struct.unpack('<i', action_stream.read(4))[0]
                                action_params['pos_y'] = struct.unpack('<i', action_stream.read(4))[0]
                                action_params['target_id1'] = _parse_object_id(action_stream)
                                action_params['target_id2'] = _parse_object_id(action_stream)
                                action_stream.read(4) 
                            elif action_id_raw == 0x19: # ACTION_USE_ABILITY_ITEM
                                action_type_str = "UseAbilityItem"
                                action_params['ability_flags'] = struct.unpack('<H', action_stream.read(2))[0]
                                object_id_str = _parse_object_id(action_stream)
                                if object_id_str.startswith('A'):
                                    action_params['ability_id'] = object_id_str
                                    action_params['item_id'] = None
                                else:
                                    action_params['item_id'] = object_id_str
                                    action_params['ability_id'] = None
                                action_params['item_ability_id2'] = _parse_object_id(action_stream) # This is likely flags or secondary ID
                                _ = action_stream.read(4) 
                                action_params['target_x'] = struct.unpack('<i', action_stream.read(4))[0]
                                action_params['target_y'] = struct.unpack('<i', action_stream.read(4))[0]
                                # Переменная длина, дочитываем остаток, если есть
                                remaining_in_action_item = cmd_data_len - action_stream.tell() 
                                if remaining_in_action_item > 0: action_stream.read(remaining_in_action_item)

                            elif action_id_raw == 0x1C: # ACTION_CHOOSE_HERO_SKILL_SUBMENU
                                action_type_str = "ChooseHeroSkillSubmenu"
                                _ = action_stream.read(1)
                            elif action_id_raw == 0x1D: # ACTION_GIVE_ITEM
                                action_type_str = "GiveItem"
                                _ = action_stream.read(1) 
                                action_params['item_id1'] = _parse_object_id(action_stream)
                                action_params['item_id2'] = _parse_object_id(action_stream)
                                action_params['target_x'] = struct.unpack('<i', action_stream.read(4))[0]
                                action_params['target_y'] = struct.unpack('<i', action_stream.read(4))[0]
                                action_params['target_object_id1'] = _parse_object_id(action_stream)
                                action_params['target_object_id2'] = _parse_object_id(action_stream)
                                action_stream.read(4)
                            elif action_id_raw == 0x1E: # ACTION_UNIT_DROP_ITEM
                                action_type_str = "UnitDropItem"
                                _ = action_stream.read(1) 
                                action_params['target_x'] = struct.unpack('<i', action_stream.read(4))[0]
                                action_params['target_y'] = struct.unpack('<i', action_stream.read(4))[0]
                                action_params['item_id1'] = _parse_object_id(action_stream)
                                action_params['item_id2'] = _parse_object_id(action_stream)
                                action_stream.read(8)
                            elif action_id_raw == 0x66: # ACTION_CHOOSE_LEVEL1_HERO_DOTA
                                action_type_str = "ChooseLevel1Hero"
                                hero_id_str = _parse_object_id(action_stream)
                                action_params['hero_id'] = hero_id_str
                                if cmd_player_id in players_map: players_map[cmd_player_id].hero_id_str = hero_id_str
                            elif action_id_raw == 0x67: # ACTION_CHOOSE_HERO_DOTA
                                action_type_str = "ChooseHero"
                                hero_id_str = _parse_object_id(action_stream)
                                action_params['hero_id'] = hero_id_str
                                if cmd_player_id in players_map: players_map[cmd_player_id].hero_id_str = hero_id_str
                            else: # Неизвестное действие
                                remaining_in_action = cmd_data_len - action_stream.tell()
                                if remaining_in_action > 0: action_stream.read(remaining_in_action)
                                elif remaining_in_action < 0: raise ReplayParsingError(f"Переполнение ActionID {action_id_raw:#02x}.")
                            
                            # Determine ability_id_str for GameAction
                            final_ability_id_str = None
                            if action_type_str in ["ChooseLevel1Hero", "ChooseHero"]:
                                final_ability_id_str = action_params.get('hero_id')
                            else:
                                final_ability_id_str = action_params.get('ability_id')

                            # Determine item_id_str for GameAction
                            # Prioritize 'item_id' (from 0x10, 0x19), then 'item_id1' (from 0x1D, 0x1E)
                            final_item_id_str = action_params.get('item_id')
                            if final_item_id_str is None: # If 'item_id' is None (e.g. for abilities, or if not set)
                                final_item_id_str = action_params.get('item_id1') # Fallback to 'item_id1'
                                
                            ga = GameAction(
                                player_id=cmd_player_id, timestamp_ms=current_time_ms,
                                timestamp_str=format_ms_to_hhmmss(current_time_ms), action_type=action_type_str,
                                ability_id_str=final_ability_id_str,
                                item_id_str=final_item_id_str,
                                target_unit_id_str=action_params.get('target_id1'),
                                x_coord=action_params.get('pos_x') or action_params.get('target_x'),
                                y_coord=action_params.get('pos_y') or action_params.get('target_y'),
                                value=action_params.get('order_id')
                            )
                            game_actions_list.append(ga)
                
                elif block_id == COMMAND_BLOCK_0x20: 
                    player_id = decompressed_data_stream.read(1)[0]
                    length = struct.unpack('<H', decompressed_data_stream.read(2))[0]
                    action_data_bytes = decompressed_data_stream.read(length)
                    if len(action_data_bytes) < length: raise ReplayParsingError("Неполные данные CommandBlock 0x20.")
                    
                    player_actions_count[player_id] = player_actions_count.get(player_id, 0) + 1

                    action_stream = io.BytesIO(action_data_bytes)
                    if action_stream.tell() < length:
                        action_id_raw = action_stream.read(1)[0]
                        if action_id_raw == CHAT_MESSAGE_ID: 
                            _ = action_stream.read(1)[0] # chat_flags
                            chat_mode_val = struct.unpack('<I', action_stream.read(4))[0]
                            chat_message_text = _read_null_terminated_string(action_stream)
                            chat_mode_str = {0x00: "All", 0x01: "Allies", 0x02: "Observers"}.get(chat_mode_val, "Unknown")
                            chat_log_list.append(ChatEntry(player_id=player_id, message_text=chat_message_text, timestamp_ms=current_time_ms, timestamp_str=format_ms_to_hhmmss(current_time_ms), mode_str=chat_mode_str))
                        else: # Другое действие внутри 0x20
                             action_stream.read(length - 1) # Пропускаем
                
                elif block_id == PLAYER_LEFT_ID:
                    player_id_left = decompressed_data_stream.read(1)[0]
                    reason, result, _ = struct.unpack('<III', decompressed_data_stream.read(12))
                    if player_id_left in players_map:
                        players_map[player_id_left].left_tick = current_time_ms
                        players_map[player_id_left].time_left_str = format_ms_to_hhmmss(current_time_ms)
                        players_map[player_id_left].left_reason_str = f"R:{reason:#0x},Res:{result:#0x}"
                
                elif block_id == GAME_END_ID: decompressed_data_stream.read(4); break 
                elif block_id in [0x1A, 0x1B, 0x1C, 0x1D]: # Sync/KeepAlive
                    if block_id == 0x1A: decompressed_data_stream.read(5) 
                    elif block_id == 0x1B: _ = _read_null_terminated_string(decompressed_data_stream) 
                    else: decompressed_data_stream.read(4) 
                else: break # Неизвестный блок

            # Заполняем actions_count для каждого игрока
            for pid, p_info_obj in players_map.items():
                p_info_obj.actions_count = player_actions_count.get(pid, 0)

            # --- 10. Создание и возврат ReplayData ---
            replay_data = ReplayData(
                game_info=game_info,
                teams=[], 
                detailed_player_reports=list(players_map.values()),
                chat_log=chat_log_list, 
                game_actions=game_actions_list 
            )
            
            # --- 11. Агрегация данных из действий ---
            from data_aggregator import aggregate_data_from_actions 
            aggregate_data_from_actions(replay_data)
            
            return replay_data

    except FileNotFoundError: raise
    except InvalidReplayFileError as e: raise
    except ReplayParsingError as e: raise
    except Exception as e: raise ReplayParsingError(f"Неожиданная ошибка: {e}")


if __name__ == '__main__':
    # Пример использования для локального тестирования
    dummy_replay_path = "dummy_test_replay_stage4.w3g" # Переименуем для нового этапа

    try:
        # --- Заголовок (68 байт для версии 0x01) ---
        header_content = REPLAY_INTRO 
        header_content += struct.pack('<I', 68)    
        header_content += struct.pack('<I', 1500)  # Compressed File Size (примерный)
        header_content += struct.pack('<I', 1)     
        header_content += struct.pack('<I', 10000) # Decompressed File Size (примерный)
        header_content += struct.pack('<I', 1)     
        header_content += GAME_IDENTIFIER_W3XP      
        header_content += struct.pack('<I', 26)    
        header_content += struct.pack('<H', 6060)  
        header_content += struct.pack('<H', 0x8000)
        header_content += struct.pack('<I', 180000) # 3 минуты
        header_content += struct.pack('<I', 0)     

        # --- Информация о блоках данных (1 блок) ---
        comp_block_size = 1500 - 68 - (2+2+4) # Размер файла - заголовок - инфо о блоке
        decomp_block_size = 10000
        
        blocks_info_content = struct.pack('<HH_I', comp_block_size, decomp_block_size, 0)

        # --- Декомпрессированные данные (для единственного блока) ---
        decompressed_payload = io.BytesIO()
        # SubHeader
        decompressed_payload.write(b'\x00') # SubHeader ID
        decompressed_payload.write(bytes([PLAYER_RECORD_ID])) 
        decompressed_payload.write(b'\x01') # Host Player ID (1)
        decompressed_payload.write(b'PlayerHost\x00') 
        decompressed_payload.write(b'\x00') # Custom Game Flag 
        
        decompressed_payload.write(b'My Test Game\x00\x00') 
        # Encoded String (простая версия для теста)
        encoded_str_source_data = io.BytesIO()
        encoded_str_source_data.write(b'\x08') # map_flags
        encoded_str_source_data.write(struct.pack('<HH_I',128,128,0x1234)) # w,h,crc
        encoded_str_source_data.write(b'Maps\\TestMap.w3x\x00')
        encoded_str_source_data.write(b'Creator\x00')
        # settings_string: speed(fast), vis(default), flags(0), placement(0), teams_together(1), locked_teams(1), shared_control(0), random_hero(0), random_races(0), checksum(CC)
        settings_bytes = bytes([0x02,0x03,0x00,0x00,0x01,0x01,0x00,0x00,0x00]) + b'\xCC' 
        encoded_str_source_data.write(settings_bytes + b'\x00') 
        
        # "Кодируем" для теста (XOR с маской)
        raw_enc_str_bytes_for_test = encoded_str_source_data.getvalue()
        truly_encoded_for_decoder_test = bytearray()
        mask_test = 0
        for byte_val_test in raw_enc_str_bytes_for_test:
            byte_val_in_file_test = byte_val_test ^ mask_test
            truly_encoded_for_decoder_test.append(byte_val_in_file_test)
            # ВАЖНО: маска для _decode_encoded_string меняется на *декодированный* байт, если *исходный* не 0.
            # Для генерации тестовых данных, нам нужно, чтобы (X ^ M1) = D1, и M2 = D1 (если X!=0).
            # То есть, X = D1 ^ M1.
            if byte_val_in_file_test != 0: # Если *закодированный* байт (тот, что в файле) не 0
                 mask_test = byte_val_test # Новая маска - это *декодированный* байт
        
        decompressed_payload.write(bytes(truly_encoded_for_decoder_test))
        decompressed_payload.write(b'\x00') # Terminator for Encoded String

        # PlayerRecords
        decompressed_payload.write(bytes([PLAYER_RECORD_ID, 0x01, *b'PlayerHost\x00', 0x00,0x01,0x00,0x64]))
        decompressed_payload.write(bytes([PLAYER_RECORD_ID, 0x02, *b'Player2\x00',    0x00,0x02,0x00,0x64]))
        
        # SlotRecords
        num_slots = 2
        decompressed_payload.write(bytes([num_slots]))
        # Slot 1: PlayerHost (ID 1, Sentinel, Blue)
        decompressed_payload.write(bytes([0x01, 0x64, SLOT_STATUS_OCCUPIED, PLAYER_TYPE_HUMAN, TEAM_SENTINEL, 0x01, 0x01,0x00,0x64]))
        # Slot 2: Player2 (ID 2, Scourge, Red)
        decompressed_payload.write(bytes([0x02, 0x64, SLOT_STATUS_OCCUPIED, PLAYER_TYPE_HUMAN, TEAM_SCOURGE, 0x00, 0x02,0x00,0x64]))

        # Meta: RandomSeed, SelectMode, StartSpotCount
        decompressed_payload.write(struct.pack('<I', 12345))
        decompressed_payload.write(b'\x01') # Select Mode (Fixed)
        decompressed_payload.write(b'\x00') # Start spot count (0)
        
        # Игровые действия (TimeSlot блоки)
        # TimeSlot 1: 5000ms
        decompressed_payload.write(bytes([0x1F])) # TIMESLOT_BLOCK_0x1F_POST_131
        #   NumBytes (для команд), TimeIncrement
        #   Внутри: PlayerID, CmdDataLen, Actions...
        #   Action: 0x67 (Choose Hero) для Player 1, Hero 'ofoh'
        action_choose_hero_p1 = bytes([0x67]) + b'hofo'[::-1] # 'ofoh'
        cmd_p1_hero = bytes([0x01]) + struct.pack('<H', len(action_choose_hero_p1)) + action_choose_hero_p1
        
        #   Action: 0x67 (Choose Hero) для Player 2, Hero 'crae'
        action_choose_hero_p2 = bytes([0x67]) + b'earc'[::-1] # 'crae'
        cmd_p2_hero = bytes([0x02]) + struct.pack('<H', len(action_choose_hero_p2)) + action_choose_hero_p2
        
        timeslot1_cmds = cmd_p1_hero + cmd_p2_hero
        decompressed_payload.write(struct.pack('<HH', len(timeslot1_cmds), 5000))
        decompressed_payload.write(timeslot1_cmds)

        # TimeSlot 2: 3000ms
        decompressed_payload.write(bytes([0x1F])) 
        #   Action: Chat message (0x20 CommandBlock -> 0x20 ChatMessageID) от Player 1
        chat_text = "Привет, мир!".encode('utf-8') + b'\x00'
        action_chat_p1_data = bytes([CHAT_MESSAGE_ID]) + b'\x00' + struct.pack('<I', 0x00) + chat_text # Flags, Mode (All)
        cmd_p1_chat = bytes([0x01]) + struct.pack('<H', len(action_chat_p1_data)) + action_chat_p1_data
        
        timeslot2_cmds = cmd_p1_chat
        decompressed_payload.write(struct.pack('<HH', len(timeslot2_cmds), 3000))
        decompressed_payload.write(timeslot2_cmds)
        
        # Player 2 Left
        decompressed_payload.write(bytes([PLAYER_LEFT_ID]))
        decompressed_payload.write(b'\x02') # PlayerID
        decompressed_payload.write(struct.pack('<III', 1, 8, 8000 + 1000)) # Reason, Result, Time (current_time_ms + 1000)


        compressed_payload_test = zlib.compress(decompressed_payload.getvalue())
        if len(compressed_payload_test) > comp_block_size:
            compressed_payload_test = compressed_payload_test[:comp_block_size]
        elif len(compressed_payload_test) < comp_block_size:
            compressed_payload_test += b'\x00' * (comp_block_size - len(compressed_payload_test))

        with open(dummy_replay_path, 'wb') as f_dummy:
            f_dummy.write(header_content)
            f_dummy.write(blocks_info_content)
            f_dummy.write(compressed_payload_test) 

        print(f"Попытка прочитать тестовый файл: {dummy_replay_path}")
        replay_data_obj = read_replay_file(dummy_replay_path)

        if replay_data_obj:
            print(f"\n--- GameInfo ---")
            gi = replay_data_obj.game_info
            print(f"  Game Name: {gi.game_name}, Map: {gi.map_name}, Speed: {gi.game_speed_str}")
            print(f"  Length: {gi.game_length_str}, Ratio: {gi.player_ratio_str}")

            print(f"\n--- Players ({len(replay_data_obj.detailed_player_reports)}) ---")
            for p_info in sorted(replay_data_obj.detailed_player_reports, key=lambda p: p.player_id):
                team_name = {TEAM_SENTINEL: "Sentinel", TEAM_SCOURGE: "Scourge"}.get(p_info.team_id, f"Team {p_info.team_id}")
                print(f"  ID={p_info.player_id}, Name='{p_info.name}', Team='{team_name}', Color='{p_info.color_str}', Hero='{p_info.hero_name} ({p_info.hero_id_str})', Level={p_info.level}, APM={p_info.apm}")
                if p_info.left_tick: print(f"    Left at: {p_info.time_left_str}, Reason: {p_info.left_reason_str}")
                
                print(f"    Stats: K={p_info.stats.kills}, D={p_info.stats.deaths}, A={p_info.stats.assists}, CS={p_info.stats.creep_kills}, Deny={p_info.stats.creep_denies}, Neutrals={p_info.stats.neutral_kills}")
                print(f"    Inventory: {p_info.items_inventory}")
                print(f"    Item Build ({len(p_info.item_build_timeline)}):")
                for item_b in p_info.item_build_timeline[:3]: print(f"      - {item_b.item_name} ({item_b.item_id_str}) @ {item_b.timestamp_str}, Cost: {item_b.cost}")
                if len(p_info.item_build_timeline) > 3: print("        ...")
                print(f"    Skill Build ({len(p_info.skill_build)}):")
                for skill_b in p_info.skill_build[:3]: print(f"      - {skill_b.skill_name} ({skill_b.ability_id_str}) LvlTakenAt: {skill_b.level_taken_at} @ {skill_b.timestamp_str}")
                if len(p_info.skill_build) > 3: print("        ...")


            print(f"\n--- Game Actions ({len(replay_data_obj.game_actions)}) ---")
            for idx, action in enumerate(replay_data_obj.game_actions[:3]): # Первые 3 действия
                print(f"  {idx+1}. Time: {action.timestamp_str}, Player: {action.player_id}, Type: {action.action_type}")
                if action.ability_id_str: print(f"     Ability/Item: {action.ability_id_str}")
                if action.target_unit_id_str: print(f"     Target Unit: {action.target_unit_id_str}")
                if action.x_coord is not None: print(f"     Coords: ({action.x_coord}, {action.y_coord})")
            if len(replay_data_obj.game_actions) > 3: print("     ...")

            print(f"\n--- Chat Log ({len(replay_data_obj.chat_log)}) ---")
            for chat_entry in replay_data_obj.chat_log[:3]: # Первые 3 сообщения
                print(f"  Time: {chat_entry.timestamp_str}, Player {chat_entry.player_id} ({chat_entry.mode_str}): {chat_entry.message_text}")
            if len(replay_data_obj.chat_log) > 3: print("     ...")
        else:
            print("\nНе удалось прочитать данные реплея.")

    except Exception as e:
        print(f"\nПроизошла ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
    finally:
        import os
        if os.path.exists(dummy_replay_path):
            # os.remove(dummy_replay_path) 
            print(f"\nТестовый файл '{dummy_replay_path}' сохранен для изучения.")
