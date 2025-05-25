# Этот модуль определяет структуры данных (классы), используемые для хранения информации о реплеях Dota.
# Классы представляют различные аспекты игры, такие как информация об игре, статистика игроков,
# сборки предметов и навыков, информация об игроках и командах, игровые действия и сообщения чата.

from typing import List, Optional

class GameInfo:
    """
    Хранит общую информацию о конкретной игре (матче).
    """
    # --- Существующие поля ---
    date_time_str: str                 # Дата и время начала игры (например, "24/05/2025 16:25")
    game_mode_code_str: str            # Игровой режим в виде кода (например, "-apomnp")
    game_length_str: str               # Продолжительность игры в текстовом виде (например, "0:58")
    player_ratio_str: str              # Соотношение игроков (например, "1v1", "5v5")
    game_score_str: str                # Счет игры (например, "0/0", "Sentinel Kills/Scourge Kills")
    winner_str: str                    # Победившая сторона (например, "Sentinel", "Scourge", "Draw")

    # --- Новые поля (по аналогии с C++ game_t) ---
    game_name: Optional[str]           # Название игры (часто имя хоста или заданное имя реплея)
    map_name: Optional[str]            # Название файла карты (например, "dota v6.83d.w3x")
    dota_version_str: Optional[str]    # Версия карты Dota (например, "6.83d")
    game_speed_str: Optional[str]      # Скорость игры (например, "Fast", "Normal")
    map_checksum_str: Optional[str]    # Контрольная сумма карты (MD5 или другая)
    game_duration_seconds: int         # Длительность игры в секундах
    game_mode_description_str: Optional[str] # Расшифровка игрового режима (например, "All Pick, Only Mid, No Powerups")

    def __init__(self, 
                 date_time_str: str, 
                 game_mode_code_str: str, 
                 game_length_str: str, 
                 player_ratio_str: str, 
                 game_score_str: str, 
                 winner_str: str,
                 game_duration_seconds: int,
                 game_name: Optional[str] = None,
                 map_name: Optional[str] = None,
                 dota_version_str: Optional[str] = None,
                 game_speed_str: Optional[str] = None,
                 map_checksum_str: Optional[str] = None,
                 game_mode_description_str: Optional[str] = None
                 ):
        """
        Инициализирует объект GameInfo.
        """
        self.date_time_str = date_time_str
        self.game_mode_code_str = game_mode_code_str
        self.game_length_str = game_length_str
        self.player_ratio_str = player_ratio_str
        self.game_score_str = game_score_str
        self.winner_str = winner_str
        self.game_duration_seconds = game_duration_seconds
        
        self.game_name = game_name
        self.map_name = map_name
        self.dota_version_str = dota_version_str
        self.game_speed_str = game_speed_str
        self.map_checksum_str = map_checksum_str
        self.game_mode_description_str = game_mode_description_str

class PlayerStats:
    """
    Хранит агрегированную статистику игрока за матч.
    Многие из этих полей могут быть рассчитаны на основе списка GameAction,
    но могут также предоставляться парсером напрямую для удобства.
    """
    # --- Существующие поля (могут быть пересмотрены при реализации парсера действий) ---
    kills: int                         # Количество убийств героев
    deaths: int                        # Количество смертей
    assists: int                       # Количество голевых передач (помощи в убийствах)
    creep_kills: int                   # Количество убитых крипов (вражеских)
    creep_denies: int                  # Количество добитых крипов (союзных)
    neutral_kills: int                 # Количество убитых нейтральных крипов

    # --- Новые поля для более детальной статистики ---
    wards_placed: Optional[int]        # Количество установленных вардов (Observer & Sentry)
    wards_killed: Optional[int]        # Количество уничтоженных вражеских вардов
    runes_picked_up: Optional[int]     # Количество подобранных рун
    hero_damage_dealt: Optional[int]   # Общий урон, нанесенный вражеским героям
    tower_damage_dealt: Optional[int]  # Общий урон, нанесенный строениям
    healing_done: Optional[int]        # Общее количество исцеления союзников (включая себя)
    gold_spent: Optional[int]          # Общее количество потраченного золота

    def __init__(self, 
                 kills: int, deaths: int, assists: int, 
                 creep_kills: int, creep_denies: int, neutral_kills: int,
                 wards_placed: Optional[int] = None,
                 wards_killed: Optional[int] = None,
                 runes_picked_up: Optional[int] = None,
                 hero_damage_dealt: Optional[int] = None,
                 tower_damage_dealt: Optional[int] = None,
                 healing_done: Optional[int] = None,
                 gold_spent: Optional[int] = None
                 ):
        """
        Инициализирует объект PlayerStats.
        """
        self.kills = kills
        self.deaths = deaths
        self.assists = assists
        self.creep_kills = creep_kills
        self.creep_denies = creep_denies
        self.neutral_kills = neutral_kills
        
        self.wards_placed = wards_placed
        self.wards_killed = wards_killed
        self.runes_picked_up = runes_picked_up
        self.hero_damage_dealt = hero_damage_dealt
        self.tower_damage_dealt = tower_damage_dealt
        self.healing_done = healing_done
        self.gold_spent = gold_spent

class ItemBuildEntry:
    """
    Представляет один элемент в истории сборки предметов игрока.
    """
    item_name: str                     # Название предмета
    timestamp_str: str                 # Временная метка приобретения предмета (например, "0:30")
    cost: int                          # Стоимость предмета в золоте
    item_id_str: str                   # Строковый ID предмета (например, "ratl", "pms", "ward")

    def __init__(self, item_name: str, timestamp_str: str, cost: int, item_id_str: str):
        """
        Инициализирует объект ItemBuildEntry.
        """
        self.item_name = item_name
        self.timestamp_str = timestamp_str
        self.cost = cost
        self.item_id_str = item_id_str

class SkillBuildEntry:
    """
    Представляет один элемент в истории прокачки способностей игрока.
    """
    skill_name: str                    # Название способности
    level_taken_at: int                # Уровень героя, на котором была взята способность
    timestamp_str: str                 # Временная метка прокачки способности (например, "0:41")
    ability_id_str: str                # Строковый ID способности (например, "A001", "A00B")

    def __init__(self, skill_name: str, level_taken_at: int, timestamp_str: str, ability_id_str: str):
        """
        Инициализирует объект SkillBuildEntry.
        """
        self.skill_name = skill_name
        self.level_taken_at = level_taken_at
        self.timestamp_str = timestamp_str
        self.ability_id_str = ability_id_str

class PlayerInfo:
    """
    Хранит подробную информацию об одном игроке в матче.
    """
    # --- Идентификация игрока ---
    player_id: int                     # Уникальный ID игрока в реплее (например, 0, 1, ...). Соответствует ID из лога действий.
    name: str                          # Имя игрока
    team_id: int                       # ID команды (0: Sentinel, 1: Scourge, 2: Нейтралы, >2: Наблюдатели и т.д.)
    color_str: str                     # Цвет игрока в игре (например, "Blue", "Teal", "#FF0000")

    # --- Информация о герое ---
    hero_name: str                     # Имя героя, которым играл игрок
    hero_id_str: str                   # Строковый ID героя (например "H001" - Human Footman, "E00A" - Kael)
    level: int                         # Финальный уровень героя

    # --- Статистика и состояние ---
    stats: PlayerStats                 # Агрегированная статистика игрока (KDA, CS, и т.д.)
    gold: int                          # Количество золота у игрока (обычно текущее или на момент выхода)
    apm: int                           # Действий в минуту (может рассчитываться из actions_count)
    actions_count: Optional[int]       # Общее количество действий игрока за время его участия в игре
    
    # --- Информация о выходе из игры ---
    time_left_str: Optional[str]       # Время, когда игрок покинул игру (если применимо, например, "0:58")
    left_tick: Optional[int]           # Тик игры (внутреннее время реплея), когда игрок покинул игру
    left_reason_str: Optional[str]     # Причина выхода игрока (например, "Disconnected", "Lost")

    # --- Сборки и инвентарь ---
    items_inventory: List[str]         # Финальный инвентарь на момент выхода или конца игры (список названий предметов)
    skill_build: List[SkillBuildEntry]
    item_build_timeline: List[ItemBuildEntry]
    
    # --- Дополнительно ---
    final_position_x: Optional[int]    # Финальная X координата героя на карте
    final_position_y: Optional[int]    # Финальная Y координата героя на карте


    def __init__(self, 
                 player_id: int, name: str, team_id: int, color_str: str,
                 hero_name: str, hero_id_str: str, level: int, 
                 stats: PlayerStats, gold: int, apm: int,
                 items_inventory: List[str], 
                 skill_build: List[SkillBuildEntry], 
                 item_build_timeline: List[ItemBuildEntry],
                 actions_count: Optional[int] = None,
                 time_left_str: Optional[str] = None,
                 left_tick: Optional[int] = None,
                 left_reason_str: Optional[str] = None,
                 final_position_x: Optional[int] = None,
                 final_position_y: Optional[int] = None
                 ):
        """
        Инициализирует объект PlayerInfo.
        """
        self.player_id = player_id
        self.name = name
        self.team_id = team_id
        self.color_str = color_str
        self.hero_name = hero_name
        self.hero_id_str = hero_id_str
        self.level = level
        self.stats = stats
        self.gold = gold
        self.apm = apm # Может быть пересчитан позже, если actions_count доступен
        self.actions_count = actions_count
        self.time_left_str = time_left_str
        self.left_tick = left_tick
        self.left_reason_str = left_reason_str
        self.items_inventory = items_inventory
        self.skill_build = skill_build
        self.item_build_timeline = item_build_timeline
        self.final_position_x = final_position_x
        self.final_position_y = final_position_y

class TeamLane:
    """
    Представляет одну линию (top, mid, bot, no lane) и игроков на ней от одной команды.
    """
    lane_name: str                     # Название линии (например, "Top", "No lane", "Roaming")
    players: List[PlayerInfo]          # Список объектов PlayerInfo игроков на этой линии

    def __init__(self, lane_name: str, players: List[PlayerInfo]):
        """
        Инициализирует объект TeamLane.
        """
        self.lane_name = lane_name
        self.players = players

class TeamInfo:
    """
    Хранит информацию о команде (Sentinel или Scourge), включая распределение игроков по линиям.
    """
    name: str                          # Название команды (например, "Sentinel", "Scourge")
    lanes: List[TeamLane]              # Список объектов TeamLane, представляющих линии команды

    def __init__(self, name: str, lanes: List[TeamLane]):
        """
        Инициализирует объект TeamInfo.
        """
        self.name = name
        self.lanes = lanes

class GameAction:
    """
    Представляет одно игровое действие, совершенное игроком.
    Это базовый класс или структура для различных типов действий.
    """
    player_id: int                     # ID игрока, совершившего действие
    timestamp_str: str                 # Временная метка действия в формате "минуты:секунды"
    timestamp_ms: int                  # Временная метка действия в миллисекундах от начала игры
    action_type: str                   # Тип действия (например, "Ability", "Attack", "Move", "SelectItem", "WardPlacement", "RunePickup")
    
    # Опциональные поля, зависящие от action_type
    target_unit_id_str: Optional[str]  # ID юнита, на которого направлено действие (если есть)
    target_item_id_str: Optional[str]  # ID предмета, связанного с действием (например, использование предмета)
    ability_id_str: Optional[str]      # ID способности (если действие - использование способности)
    item_id_str: Optional[str]         # ID предмета (например, при покупке, продаже, поднятии)
    
    x_coord: Optional[int]             # Координата X на карте (для движения, указания цели и т.д.)
    y_coord: Optional[int]             # Координата Y на карте
    
    value: Optional[int]               # Дополнительное числовое значение (например, ID приказа, выбранный юнит)
    
    # Флаги для семантического анализа действий (могут заполняться на этапе постобработки)
    is_kill_event: bool = False        # True, если это действие непосредственно привело к убийству героя
    is_death_event: bool = False       # True, если это действие является смертью героя (событие смерти)
    is_cs_event: bool = False          # True, если это действие - успешный ластхит крипа
    is_deny_event: bool = False        # True, если это действие - успешный денай крипа/башни
    is_ward_event: bool = False        # True, если связано с вардом (постановка, убийство)
    is_rune_pickup_event: bool = False # True, если это подбор руны

    def __init__(self, 
                 player_id: int, 
                 timestamp_str: str, 
                 timestamp_ms: int,
                 action_type: str,
                 target_unit_id_str: Optional[str] = None,
                 target_item_id_str: Optional[str] = None,
                 ability_id_str: Optional[str] = None,
                 item_id_str: Optional[str] = None,
                 x_coord: Optional[int] = None,
                 y_coord: Optional[int] = None,
                 value: Optional[int] = None
                 ):
        """
        Инициализирует объект GameAction.
        """
        self.player_id = player_id
        self.timestamp_str = timestamp_str
        self.timestamp_ms = timestamp_ms
        self.action_type = action_type
        self.target_unit_id_str = target_unit_id_str
        self.target_item_id_str = target_item_id_str
        self.ability_id_str = ability_id_str
        self.item_id_str = item_id_str
        self.x_coord = x_coord
        self.y_coord = y_coord
        self.value = value
        # Семантические флаги инициализируются как False по умолчанию

class ChatEntry:
    """
    Представляет одно сообщение в игровом чате.
    """
    player_id: int                     # ID игрока, отправившего сообщение. Может быть специальное значение для системных сообщений.
    message_text: str                  # Текст сообщения.
    timestamp_str: str                 # Временная метка сообщения в формате "минуты:секунды".
    timestamp_ms: int                  # Временная метка сообщения в миллисекундах от начала игры.
    mode_str: str                      # Режим чата ("All", "Team", "Observer", "System").

    def __init__(self, 
                 player_id: int, 
                 message_text: str, 
                 timestamp_str: str, 
                 timestamp_ms: int,
                 mode_str: str):
        """
        Инициализирует объект ChatEntry.
        """
        self.player_id = player_id
        self.message_text = message_text
        self.timestamp_str = timestamp_str
        self.timestamp_ms = timestamp_ms
        self.mode_str = mode_str

class ReplayData:
    """
    Корневой объект, агрегирующий всю информацию, извлеченную из реплея.
    """
    game_info: GameInfo                             # Общая информация об игре
    teams: List[TeamInfo]                           # Список информации о командах (Sentinel, Scourge)
    detailed_player_reports: List[PlayerInfo]       # Список подробной информации по каждому игроку (для отчетов)
    
    # --- Новые поля для хранения детальных логов ---
    chat_log: List[ChatEntry]                       # Полный лог игрового чата
    game_actions: List[GameAction]                  # Полный лог игровых действий

    def __init__(self, 
                 game_info: GameInfo, 
                 teams: List[TeamInfo], 
                 detailed_player_reports: List[PlayerInfo],
                 chat_log: List[ChatEntry],
                 game_actions: List[GameAction]
                 ):
        """
        Инициализирует объект ReplayData.
        """
        self.game_info = game_info
        self.teams = teams
        self.detailed_player_reports = detailed_player_reports
        self.chat_log = chat_log
        self.game_actions = game_actions
