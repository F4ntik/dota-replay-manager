# Этот модуль отвечает за форматирование данных реплея в текстовый вид.

from data_structures import ReplayData, PlayerInfo, TeamLane, TeamInfo, SkillBuildEntry, ItemBuildEntry

def _format_player_info_short(player: PlayerInfo) -> str:
    """
    Форматирует краткую информацию об игроке для использования в списках команд.

    Args:
        player (PlayerInfo): Объект с данными игрока.

    Returns:
        str: Однострочное текстовое представление краткой информации об игроке.
    """
    return (
        f"  {player.name} - {player.hero_name}, level {player.level:<18} "
        f"K/D/A: {player.stats.kills}/{player.stats.deaths}/{player.stats.assists:<10} "
        f"C/D/N: {player.stats.creep_kills}/{player.stats.creep_denies}/{player.stats.neutral_kills:<12} "
        f"{str(player.gold) + ' gold':>10} {str(player.apm) + ' apm':>7} "
        f"left: {player.time_left_str:<6} items: [{', '.join(player.items_inventory)}]"
    )

def _format_skill_build(skill_build: list[SkillBuildEntry]) -> str:
    """
    Форматирует информацию о прокачке способностей игрока в многострочный блок.
    Если способностей нет, возвращает пустую строку.

    Args:
        skill_build (list[SkillBuildEntry]): Список записей о прокачке способностей.

    Returns:
        str: Многострочное текстовое представление прокачки способностей или пустая строка.
    """
    if not skill_build:
        return ""  # Пустая строка, если список навыков пуст
    lines = []
    for skill_entry in skill_build:
        lines.append(f"   {skill_entry.level_taken_at}. {skill_entry.skill_name:<25} {skill_entry.timestamp_str}")
    return "\n".join(lines)

def _format_item_build(item_build: list[ItemBuildEntry]) -> str:
    """
    Форматирует информацию о сборке предметов игрока в многострочный блок.
    Если предметов нет, возвращает пустую строку.

    Args:
        item_build (list[ItemBuildEntry]): Список записей о сборке предметов.

    Returns:
        str: Многострочное текстовое представление сборки предметов или пустая строка.
    """
    if not item_build:
        return ""  # Пустая строка, если список предметов пуст
    lines = []
    for item_entry in item_build:
        lines.append(f"  {item_entry.item_name:<30} {item_entry.timestamp_str:<7} {item_entry.cost} gold")
    return "\n".join(lines)

def format_replay_to_text(replay_data: ReplayData) -> str:
    """
    Форматирует данные реплея в многострочную строку.

    Args:
        replay_data: Объект ReplayData с данными реплея.

    Returns:
        Многострочная строка с отформатированными данными реплея.
    """
    output_lines = []

    # Информация об игре
    game_info = replay_data.game_info
    output_lines.append(f"Date: {game_info.date_time_str}")
    output_lines.append(f"Game mode: {game_info.game_mode}")
    output_lines.append(f"Game length: {game_info.game_length_str}")
    output_lines.append(f"Players: {game_info.player_ratio_str}")
    output_lines.append(f"Game score: {game_info.game_score_str}")
    output_lines.append(f"Winner: {game_info.winner_str}")
    output_lines.append("") # Пустая строка

    # Информация о командах
    for team in replay_data.teams:
        output_lines.append(f"{team.name}:")
        for lane in team.lanes:
            output_lines.append(f" {lane.lane_name}")
            for player in lane.players:
                output_lines.append(_format_player_info_short(player))
        output_lines.append("")  # Пустая строка после каждой команды, кроме последней, или всегда? Судя по примеру - всегда.

    # Детальные отчеты по игрокам
    # В примере вывода нет пустой строки перед первым детальным отчетом, если он идет сразу после команд.
    # Но если команд нет (что маловероятно), то пустая строка была бы уместна.
    # Однако, если следовать примеру, пустая строка ставится *после* блока команд, а не *перед* блоком детальных отчетов.

    for player_report in replay_data.detailed_player_reports:
        output_lines.append(f"Detailed report for {player_report.name} - {player_report.hero_name}:")
        output_lines.append("Skill build:")
        output_lines.append(_format_skill_build(player_report.skill_build))
        output_lines.append("Item build:")
        output_lines.append(_format_item_build(player_report.item_build_timeline))
        output_lines.append("") # Пустая строка после каждого детального отчета

    # Убираем последнюю пустую строку, если она есть, чтобы точно соответствовать примеру
    # В примере после последнего блока Item build нет дополнительной пустой строки
    if output_lines and output_lines[-1] == "":
        output_lines.pop()
        
    return "\n".join(output_lines)
