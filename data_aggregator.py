# Этот модуль отвечает за агрегацию и вычисление производных данных
# на основе списка игровых действий (GameAction), полученного из парсера реплеев.

from typing import Dict, List, Optional
from data_structures import (
    ReplayData, PlayerInfo, PlayerStats, ItemBuildEntry, SkillBuildEntry, GameAction
)

# Предполагаемые ActionID или типы действий для различных событий.
# Эти значения должны быть синхронизированы с теми, что используются в replay_reader.py
ACTION_TYPE_CHOOSE_HERO = "ChooseHero" 
ACTION_TYPE_CHOOSE_LEVEL1_HERO = "ChooseLevel1Hero"
ACTION_TYPE_USE_ABILITY_ITEM = "UseAbilityItem"
ACTION_TYPE_LEARN_SKILL = "LearnSkill" # Гипотетический тип, если replay_reader его выставляет
# ID способностей для изучения (часто это ID самой способности)
# ID предметов для покупки/получения

# Заглушки для справочников ID (в будущем их нужно будет заполнить)
HERO_ID_TO_NAME: Dict[str, str] = {
    "hfoo": "Footman", # Пример
    "earc": "Archer", # Пример
    "ofoh": "Hero Farseer", # Пример Farseer ID из теста
    "crae": "Hero Crypt Lord", # Пример Crypt Lord ID из теста
}
ABILITY_ID_TO_NAME: Dict[str, str] = {
    "A001": "Some Skill Lvl 1", # Пример
    "A002": "Some Skill Lvl 2", # Пример
}
ITEM_ID_TO_NAME: Dict[str, str] = {
    "ratl": "Robe of the Magi", # Пример
    "pms": "Poor Man's Shield", # Пример
}
ITEM_ID_TO_COST: Dict[str, int] = {
    "ratl": 450, # Пример
    "pms": 550,  # Пример
}
# Список ID расходуемых предметов (для упрощенного управления инвентарем)
CONSUMABLE_ITEM_IDS: List[str] = ["tpsc", "poti", "ward"] # Scroll, Clarity, Observer/Sentry Ward


def aggregate_data_from_actions(replay_data: ReplayData) -> None:
    """
    Агрегирует данные из списка игровых действий (game_actions) и обогащает
    объекты PlayerInfo и PlayerStats производной информацией.

    Модифицирует объект replay_data по месту.

    Args:
        replay_data (ReplayData): Объект с данными реплея.
    """
    if not replay_data or not replay_data.detailed_player_reports:
        return

    players_map: Dict[int, PlayerInfo] = {p.player_id: p for p in replay_data.detailed_player_reports}

    # 1. Инициализация и сброс агрегируемых полей
    for player in replay_data.detailed_player_reports:
        player.skill_build = [] # Очищаем, т.к. будем заполнять заново
        player.item_build_timeline = [] # Очищаем
        player.items_inventory = [] # Очищаем
        
        # PlayerStats должен быть уже инициализирован в PlayerInfo конструкторе.
        # Сбрасываем значения, которые будут пересчитаны или агрегированы.
        player.stats.kills = 0
        player.stats.deaths = 0
        player.stats.assists = 0
        player.stats.creep_kills = 0
        player.stats.creep_denies = 0
        player.stats.neutral_kills = 0
        player.level = 1 # Начальный уровень, будет обновляться (упрощенно)
        # player.apm и player.actions_count обрабатываются в конце

    # 2. Итерация по replay_data.game_actions
    for action in replay_data.game_actions:
        player = players_map.get(action.player_id)
        if not player:
            continue 

        # --- Обработка выбора героя ---
        if action.action_type == ACTION_TYPE_CHOOSE_HERO or \
           action.action_type == ACTION_TYPE_CHOOSE_LEVEL1_HERO:
            hero_id = action.ability_id_str or action.item_id_str # В replay_reader.py мы кладем ID героя сюда
            if hero_id:
                player.hero_id_str = hero_id
                player.hero_name = HERO_ID_TO_NAME.get(hero_id, hero_id)

        # --- Обработка изучения способностей ---
        # Предполагаем, что replay_reader.py может выставлять action_type = ACTION_TYPE_LEARN_SKILL
        # или мы анализируем ACTION_TYPE_USE_ABILITY_ITEM.
        # Для DotA, изучение - это использование способности с ID вида 'AXXX' на самого себя,
        # или специфичные ActionID для изучения.
        # Здесь упрощенно: если действие это "UseAbilityItem" и есть ability_id_str, считаем это изучением.
        # Более точная логика потребует анализа ID способностей (например, только те, что можно изучать).
        if (action.action_type == ACTION_TYPE_USE_ABILITY_ITEM or action.action_type == ACTION_TYPE_LEARN_SKILL) and \
           action.ability_id_str:
            # Это очень грубое допущение. Нужен список ID способностей, которые являются "изучаемыми".
            # Также нужно отличать изучение от простого использования.
            # Пока что, если способность не предмет и не атака, добавим.
            # Исключим предметы, которые могут быть в ability_id_str по ошибке парсера или для активации.
            # Исключим базовые атаки, если они имеют ID.
            # ID способностей в DotA обычно начинаются с 'A'.
            if action.ability_id_str.startswith('A'): 
                skill_id = action.ability_id_str
                skill_name = ABILITY_ID_TO_NAME.get(skill_id, skill_id)
                
                # Определение уровня героя: очень упрощенно, по количеству уже изученных способностей.
                # Это не отражает реальный уровень героя, а скорее порядок изучения.
                # Реальный уровень героя должен отслеживаться по событиям повышения уровня или опыту.
                # Пока используем это как заглушку для "level_taken_at".
                current_skill_points_spent = len(player.skill_build)
                # Предположим, что игрок начинает с 1 уровнем и может изучить способность.
                # Каждый скилл-поинт соответствует повышению уровня в упрощенной модели.
                approx_hero_level_for_skill = current_skill_points_spent + 1
                
                # Проверка на дубликаты (изучение той же способности на том же "уровне")
                # Это не предотвратит изучение разных уровней одной способности.
                is_duplicate_for_level = any(
                    entry.ability_id_str == skill_id and entry.level_taken_at == approx_hero_level_for_skill
                    for entry in player.skill_build
                )

                if not is_duplicate_for_level:
                    entry = SkillBuildEntry(
                        skill_name=skill_name,
                        level_taken_at=approx_hero_level_for_skill, # Заглушка!
                        timestamp_str=action.timestamp_str,
                        ability_id_str=skill_id
                    )
                    player.skill_build.append(entry)
                    # Упрощенно инкрементируем уровень игрока при изучении способности
                    # Это очень неточно, но для примера.
                    if player.level < 25: # Максимальный уровень (примерный)
                        player.level = max(player.level, approx_hero_level_for_skill)


        # --- Обработка покупки/получения предметов ---
        # Предполагаем, что покупка предмета также может быть ACTION_TYPE_USE_ABILITY_ITEM,
        # где item_id_str содержит ID купленного предмета.
        if action.action_type == ACTION_TYPE_USE_ABILITY_ITEM and action.item_id_str:
            # ID предметов могут быть разными (ratl, pms, ward, blink, etc.)
            item_id = action.item_id_str
            item_name = ITEM_ID_TO_NAME.get(item_id, item_id)
            item_cost = ITEM_ID_TO_COST.get(item_id, 0) 

            item_entry = ItemBuildEntry(
                item_name=item_name,
                timestamp_str=action.timestamp_str,
                cost=item_cost,
                item_id_str=item_id
            )
            player.item_build_timeline.append(item_entry)
            
            # Обновление инвентаря (упрощенное)
            # Добавляем нерасходуемые предметы, если есть место.
            # Не учитываем продажу, передачу, стаки, курьера.
            if item_id not in CONSUMABLE_ITEM_IDS:
                if len(player.items_inventory) < 6: # Обычно 6 слотов в основном инвентаре
                    player.items_inventory.append(item_name)
            # Если это расходуемый, он используется и не попадает в финальный инвентарь таким образом.
            # Логика использования расходуемых (например, танго, варды) должна быть сложнее.

        # --- Подсчет K/D/A, C/D/N ---
        # ЗАГЛУШКА: На данном этапе эти статистики не подсчитываются из действий.
        # Это требует детального анализа смертей юнитов и атрибуции этих событий.
        # replay_reader должен выставлять семантические флаги в GameAction (is_kill_event и т.д.).
        # if action.is_kill_event and action.target_is_hero: player.stats.kills += 1
        # if action.is_death_event and action.player_id == player.player_id: player.stats.deaths += 1
        # if action.is_cs_event: player.stats.creep_kills += 1
        # if action.is_deny_event: player.stats.creep_denies += 1
        # if action.is_neutral_kill_event: player.stats.neutral_kills += 1

        # --- Определение уровня героя (PlayerInfo.level) ---
        # ЗАГЛУШКА: Уровень героя упрощенно обновляется при изучении способностей (см. выше).
        # Реальный подсчет уровня требует отслеживания опыта.

    # 3. Финальный инвентарь (упрощенная версия уже сделана выше при покупке)
    # Для более точного финального инвентаря, нужно было бы отслеживать:
    # - Продажу предметов
    # - Смерть и потерю предметов (если применимо в моде)
    # - Использование расходуемых предметов (танго, варды, фласки)
    # - Перемещение предметов в курьера или тайник (stash)
    # - Поднятие выброшенных предметов
    # Текущая реализация просто добавляет нерасходуемые предметы в список до 6 штук.

    # 4. Подсчет APM
    # Предполагается, что PlayerInfo.actions_count заполняется в replay_reader.py
    # на основе всех релевантных действий игрока.
    for player in replay_data.detailed_player_reports:
        if player.actions_count is not None and player.actions_count > 0:
            player_duration_seconds = replay_data.game_info.game_duration_seconds
            if player.left_tick is not None: # Если игрок вышел раньше
                player_duration_seconds = player.left_tick // 1000
            
            if player_duration_seconds > 0:
                player.apm = round((player.actions_count / player_duration_seconds) * 60)
            elif player.actions_count > 0 : # Если длительность 0, но действия есть (очень короткая игра/выход)
                player.apm = player.actions_count # APM = кол-во действий за "минуту" = 0
            else:
                player.apm = 0
        else: # Если actions_count не был посчитан или равен 0
            player.apm = 0
            if player.actions_count is None: # Инициализируем, если не было
                 player.actions_count = 0


    # 5. Заполнение PlayerStats (K/D/A, C/D/N) - сейчас это заглушки, остаются нулями.
    # Если бы они подсчитывались, здесь бы происходила финальная запись в player.stats.
    # Например: player.stats.kills = calculated_kills_for_player

    # Примечание: Формирование TeamInfo с распределением по линиям (TeamLane)
    # требует дополнительной логики анализа позиций героев или других эвристик.
    # На данном этапе мы просто распределяем игроков по командам Sentinel/Scourge
    # в одну общую "No lane".

    # 5. Формирование информации о командах (replay_data.teams)
    sentinel_players = []
    scourge_players = []

    # Константы team_id должны быть доступны здесь или переданы.
    # Предположим, что TEAM_SENTINEL = 0 и TEAM_SCOURGE = 1 определены
    # в data_structures.py или импортированы сюда.
    # Для безопасности, можно использовать числовые литералы, если они стабильны.
    # (В replay_reader.py они определены, но data_aggregator их не видит напрямую)
    # Лучше импортировать их или передавать. Но для простоты сейчас используем литералы.
    TEAM_ID_SENTINEL = 0
    TEAM_ID_SCOURGE = 1
    # TEAM_ID_OBSERVER = 0x0C # Пример

    for player in replay_data.detailed_player_reports:
        if player.team_id == TEAM_ID_SENTINEL:
            sentinel_players.append(player)
        elif player.team_id == TEAM_ID_SCOURGE:
            scourge_players.append(player)
        # Игроки-наблюдатели или с другими team_id пока игнорируются для этих двух команд

    sentinel_lane = TeamLane(lane_name="No lane", players=sentinel_players)
    sentinel_team = TeamInfo(name="Sentinel", lanes=[sentinel_lane])

    scourge_lane = TeamLane(lane_name="No lane", players=scourge_players)
    scourge_team = TeamInfo(name="Scourge", lanes=[scourge_lane])

    replay_data.teams = [sentinel_team, scourge_team]

```
