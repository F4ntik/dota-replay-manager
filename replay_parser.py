# Этот модуль отвечает за "парсер" файлов реплеев.
# В текущей реализации это заглушка, которая возвращает заранее подготовленные данные.

from data_structures import (
    GameInfo, PlayerStats, ItemBuildEntry, SkillBuildEntry,
    PlayerInfo, TeamLane, TeamInfo, ReplayData
)
from typing import List

def parse_replay_file(replay_filename: str) -> ReplayData:
    """
    Заглушка функции парсинга файла реплея.

    В текущей реализации эта функция не производит реальный парсинг файла.
    Вместо этого она возвращает заранее подготовленный объект ReplayData,
    содержащий данные, максимально приближенные к примеру из описания задачи.
    Это позволяет тестировать модули форматирования (`text_formatter`, `json_formatter`)
    без необходимости иметь реальный парсер реплеев.

    Args:
        replay_filename (str): Имя файла реплея. В данной заглушке этот параметр не используется.

    Returns:
        ReplayData: Объект, содержащий тестовые данные реплея.
    """
    # Комментарий: Дальнейший код инициализирует и возвращает заранее подготовленные данные.

    # --- Игрок 1: Mep3ocTb (Naga Siren) ---
    player1_stats = PlayerStats(
        kills=0, deaths=0, assists=0, 
        creep_kills=0, creep_denies=0, neutral_kills=0
    )
    
    player1_item_build: List[ItemBuildEntry] = [
        ItemBuildEntry(item_name="Scroll of Town Portal", timestamp_str="0:30", cost=100),
        ItemBuildEntry(item_name="Sentry Wards", timestamp_str="0:30", cost=200),
        ItemBuildEntry(item_name="Ogre Axe", timestamp_str="0:36", cost=1000),
        ItemBuildEntry(item_name="Ogre Axe", timestamp_str="0:36", cost=1000), # В примере дважды
        ItemBuildEntry(item_name="Ring of Protection", timestamp_str="0:39", cost=200),
        ItemBuildEntry(item_name="Boots of Speed", timestamp_str="0:53", cost=450),
    ]
    
    player1_skill_build: List[SkillBuildEntry] = [
        SkillBuildEntry(skill_name="Ensnare", level_taken_at=1, timestamp_str="0:41")
    ]
    
    # Инвентарь в примере соответствует концу item_build_timeline для этого игрока,
    # но Sentry Wards указаны 3 раза, хотя куплены 1 раз (стак из 2).
    # Для точности с примером вывода, будем использовать то, что в примере.
    player1_inventory: List[str] = ["Ogre Axe", "Ogre Axe", "Boots of Speed", "Sentry Wards", "Sentry Wards", "Sentry Wards"]

    player1 = PlayerInfo(
        name="Mep3ocTb",
        hero_name="Naga Siren",
        level=1, # В примере уровень 1
        stats=player1_stats,
        gold=0, # В примере 0 gold для Mep3ocTb в кратком списке, но это может быть текущий голд, а не заработанный
        apm=0,  # APM не указан в примере для краткого списка, ставим 0
        time_left_str="0:58", # Время выхода
        items_inventory=player1_inventory,
        skill_build=player1_skill_build,
        item_build_timeline=player1_item_build
    )

    # --- Игрок 2: Computer (Easy) (без героя) ---
    player2_stats = PlayerStats(
        kills=0, deaths=0, assists=0, 
        creep_kills=0, creep_denies=0, neutral_kills=0
    )
    
    player2_item_build: List[ItemBuildEntry] = [] # Пусто для компьютера в примере
    player2_skill_build: List[SkillBuildEntry] = [] # Пусто для компьютера в примере
    player2_inventory: List[str] = [] # Пусто для компьютера в примере

    player2 = PlayerInfo(
        name="Computer (Easy)",
        hero_name="", # Герой - пустая строка, как в примере
        level=0, # Уровень 0, как в примере для компьютера
        stats=player2_stats,
        gold=0, # Gold 0 для Computer (Easy)
        apm=0,  # APM 0 для Computer (Easy)
        time_left_str="0:00", # Время выхода 0:00, как в примере
        items_inventory=player2_inventory,
        skill_build=player2_skill_build,
        item_build_timeline=player2_item_build
    )
    
    # --- Информация о командах ---
    # В примере у каждой команды по одному игроку и одна "No lane"
    sentinel_lane = TeamLane(lane_name="No lane", players=[player1])
    sentinel_team = TeamInfo(name="Sentinel", lanes=[sentinel_lane])

    scourge_lane = TeamLane(lane_name="No lane", players=[player2])
    scourge_team = TeamInfo(name="Scourge", lanes=[scourge_lane])

    # --- Общая информация об игре ---
    game_info = GameInfo(
        date_time_str="24/05/2025 16:25",
        game_mode="-om", # Only Mid
        game_length_str="0:58",
        player_ratio_str="1v1",
        game_score_str="0/0", # Kills Sentinel / Kills Scourge
        winner_str="Draw" # Ничья
    )

    # --- Собираем все в ReplayData ---
    # Детальные отчеты в примере есть для Mep3ocTb, но не для Computer (Easy).
    # Однако, для полноты тестирования форматеров, логично было бы создать детальный отчет
    # и для компьютера, даже если он будет содержать пустые списки навыков/предметов.
    # В задании указано "detailed_player_reports=[player1, player2]", что подразумевает отчеты для обоих.
    replay_data = ReplayData(
        game_info=game_info,
        teams=[sentinel_team, scourge_team],
        detailed_player_reports=[player1, player2] # Включаем обоих игроков в детальные отчеты
    )

    return replay_data
