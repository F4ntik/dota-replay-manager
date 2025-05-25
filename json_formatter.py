# Этот модуль отвечает за форматирование данных реплея в JSON вид.

import json
from data_structures import ReplayData, PlayerInfo, TeamLane, TeamInfo, SkillBuildEntry, ItemBuildEntry

def _convert_player_info_to_dict_short(player: PlayerInfo) -> dict:
    """
    Конвертирует объект PlayerInfo в словарь с краткой информацией об игроке,
    предназначенный для сериализации в JSON.

    Args:
        player (PlayerInfo): Объект с данными игрока.

    Returns:
        dict: Словарь с основной информацией об игроке.
    """
    return {
        "name": player.name,
        "hero": player.hero_name,
        "level": player.level,
        "kda": f"{player.stats.kills}/{player.stats.deaths}/{player.stats.assists}",
        "cdn": f"{player.stats.creep_kills}/{player.stats.creep_denies}/{player.stats.neutral_kills}",
        "gold": player.gold,
        "apm": player.apm,
        "time_left": player.time_left_str,
        "final_inventory": player.items_inventory
    }

def _convert_skill_build_entry_to_dict(skill_entry: SkillBuildEntry) -> dict:
    """
    Конвертирует объект SkillBuildEntry в словарь для JSON.

    Args:
        skill_entry (SkillBuildEntry): Запись о прокачке способности.

    Returns:
        dict: Словарь с данными о прокачанном навыке.
    """
    return {
        "level_taken": skill_entry.level_taken_at,
        "skill_name": skill_entry.skill_name,
        "time": skill_entry.timestamp_str
    }

def _convert_item_build_entry_to_dict(item_entry: ItemBuildEntry) -> dict:
    """
    Конвертирует объект ItemBuildEntry в словарь для JSON.

    Args:
        item_entry (ItemBuildEntry): Запись о приобретенном предмете.

    Returns:
        dict: Словарь с данными о предмете.
    """
    return {
        "item_name": item_entry.item_name,
        "time": item_entry.timestamp_str,
        "cost": item_entry.cost
    }

def _convert_player_details_to_dict(player: PlayerInfo) -> dict:
    """
    Конвертирует объект PlayerInfo в детализированный словарь,
    включая историю прокачки навыков и сборки предметов, для JSON.

    Args:
        player (PlayerInfo): Объект с данными игрока.

    Returns:
        dict: Словарь с подробной информацией об игроке.
    """
    return {
        "name": player.name,
        "hero": player.hero_name,
        "skill_build": [_convert_skill_build_entry_to_dict(skill) for skill in player.skill_build],
        "item_build": [_convert_item_build_entry_to_dict(item) for item in player.item_build_timeline]
    }

def format_replay_to_json(replay_data: ReplayData) -> str:
    """
    Форматирует данные реплея в JSON-строку.

    Args:
        replay_data: Объект ReplayData с данными реплея.

    Returns:
        JSON-строка с отформатированными данными реплея.
    """
    game_info = replay_data.game_info
    
    # Формируем словарь с данными реплея
    output_dict = {
        "game_overview": {
            "date": game_info.date_time_str,
            "game_mode": game_info.game_mode,
            "game_length": game_info.game_length_str,
            "players_ratio": game_info.player_ratio_str,
            "score": game_info.game_score_str,
            "winner": game_info.winner_str
        },
        "teams": [],
        "player_details": []
    }

    # Информация о командах
    for team_info in replay_data.teams:
        team_dict = {
            "team_name": team_info.name,
            "lanes": []
        }
        for lane_info in team_info.lanes:
            lane_dict = {
                "lane_name": lane_info.lane_name,
                "players": [_convert_player_info_to_dict_short(player) for player in lane_info.players]
            }
            team_dict["lanes"].append(lane_dict)
        output_dict["teams"].append(team_dict)

    # Детальные отчеты по игрокам
    for player_report in replay_data.detailed_player_reports:
        output_dict["player_details"].append(_convert_player_details_to_dict(player_report))

    # Сериализуем словарь в JSON-строку
    return json.dumps(output_dict, indent=2, ensure_ascii=False)
