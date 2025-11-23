import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

@dataclass
class HeroStatus:
    name: str
    player_name: str
    team: str # "blue" (ally) or "red" (enemy)
    role: str # 上路, 打野, 中路, 辅助, 下路
    level: int
    hp_percent: float
    mana_percent: float
    is_dead: bool = False
    respawn_time: int = 0
    position: Optional[Tuple[float, float]] = None
    kda: Tuple[int, int, int] = (0, 0, 0)
    gold: int = 0
    items: List[str] = field(default_factory=list)
    has_ult: bool = False # "没有大招" -> False
    buffs: List[str] = field(default_factory=list)

@dataclass
class TowerStatus:
    team: str # "blue" or "red"
    lane: str # 上路, 中路, 下路
    tower_type: str # 一塔, 二塔, 高地塔
    hp_percent: float
    position: Tuple[float, float]
    is_destroyed: bool = False

@dataclass
class MinionStatus:
    team: str
    lane: str
    position: Tuple[float, float]
    count: int
    hp_percent: float
    minion_type: str # 普通小兵, 炮车, 主宰先锋

@dataclass
class MonsterStatus:
    name: str
    position: Tuple[float, float]
    hp_percent: float
    exists: bool
    description: str = ""
    respawn_time: Optional[int] = None

@dataclass
class MatchState:
    time_str: str
    blue_kills: int
    red_kills: int
    blue_gold: int
    red_gold: int
    heroes: List[HeroStatus] = field(default_factory=list)
    towers: List[TowerStatus] = field(default_factory=list)
    minions: List[MinionStatus] = field(default_factory=list)
    monsters: List[MonsterStatus] = field(default_factory=list)

class MatchParser:
    def parse(self, text: str) -> MatchState:
        lines = text.split('\n')
        current_section = None
        
        match_state = MatchState(
            time_str="00:00", 
            blue_kills=0, red_kills=0, 
            blue_gold=0, red_gold=0
        )

        # Store static tower info first
        static_towers = {} # key: (team, lane, type) -> (x, y)

        # Helper to extract coordinate from string like "(12.3, 45.6)"
        def parse_coord(s):
            try:
                parts = s.replace('（', '(').replace('）', ')').strip('()').split(',')
                return float(parts[0]), float(parts[1])
            except:
                return None

        # First pass: get static map info if available
        for line in lines:
            if line.strip().startswith('[地图信息]'):
                current_section = "地图信息"
                continue
            if line.strip().startswith('['):
                current_section = None
                continue
            
            if current_section == "地图信息":
                 # Parse tower coordinates
                 # 我方防御塔坐标为：蓝方上路一塔(-52.4, 28.7)、...
                 # 敌方防御塔坐标为：红方...
                 matches = re.findall(r'(蓝方|红方)([^防御塔\d]+)(一塔|二塔|高地塔)[（\(]([\d\.-]+)[,，]\s*([\d\.-]+)[）\)]', line)
                 for m in matches:
                     team_code = "blue" if m[0] == "蓝方" else "red"
                     lane = m[1]
                     t_type = m[2]
                     x, y = float(m[3]), float(m[4])
                     static_towers[(team_code, lane, t_type)] = (x, y)

        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                continue

            if current_section == "整体情况":
                if "游戏阶段" in line:
                    # Extract time "13分4秒" -> "13:04"
                    match = re.search(r'(\d+)分(\d+)秒', line)
                    if match:
                        match_state.time_str = f"{match.group(1)}:{match.group(2).zfill(2)}"
            
            elif current_section == "总体态势":
                if "我方人头数" in line:
                    parts = line.split('，')
                    for p in parts:
                        if "我方人头数" in p:
                            val_str = p.split('：')[1]
                            match_state.blue_kills = int(re.search(r'\d+', val_str).group())
                        elif "敌方人头数" in p:
                            val_str = p.split('：')[1]
                            match_state.red_kills = int(re.search(r'\d+', val_str).group())
                elif "我方总经济" in line:
                     parts = line.split('，')
                     for p in parts:
                        if "我方总经济" in p:
                            val_str = p.split('：')[1]
                            match_state.blue_gold = int(re.search(r'\d+', val_str).group())
                        elif "敌方总经济" in p:
                            val_str = p.split('：')[1]
                            match_state.red_gold = int(re.search(r'\d+', val_str).group())

            elif current_section in ["玩家情况", "我方英雄状态", "视野可见的敌方英雄", "视野不可见的敌方英雄", "阵亡英雄"]:
                # Parse hero lines
                # Format: <我方-玩家-廉颇>...
                if line.startswith('<'):
                    self._parse_hero_line(line, match_state)
            
            elif current_section == "防御塔与兵线状态":
                 self._parse_tower_minion_line(line, match_state, static_towers)
            
            elif current_section == "野怪状态":
                # Example:
                # 核心中立野怪：主宰，坐标（-18.50，23.30）：不存在，29秒后刷新；暴君，坐标（18.20，-23.70）：存在血量100%...
                # 存活可见野怪：我方蓝buff，坐标（-29.60，3.90），血量87%（正在被攻击）。；敌方蓝buff...
                
                segments = line.split('；')
                for seg in segments:
                    # Cleanup
                    seg = seg.strip().strip('。')
                    if not seg: continue
                    
                    # Try to find monster patterns
                    # Pattern 1: Name, Coord, Status
                    # Need to handle "核心中立野怪：" prefix
                    if "：" in seg and ("不存在" in seg or "存在" in seg or "血量" in seg):
                        # Split by colon might be tricky because of multiple colons
                        # Use regex to find name and coord first
                        # 核心中立野怪：主宰，坐标（...）
                        # Or simply: 主宰，坐标（...）
                        
                        # Try to extract name and coord
                        # Names: 主宰, 暴君, 风暴龙王, 我方蓝buff, 敌方蓝buff, 我方红buff, 敌方红buff
                        
                        # Regex to catch name and coord
                        # Note: Name might be preceded by "核心中立野怪：" or "存活可见野怪："
                        
                        # Strategy: Find "Name" which is usually before "，坐标"
                        # But "Name" might follow "："
                        
                        # Let's iterate through known monster names to be safer, or try general regex
                        known_monsters = ["主宰", "暴君", "风暴龙王", "我方蓝buff", "敌方蓝buff", "我方红buff", "敌方红buff"]
                        
                        current_monster = None
                        current_coord = None
                        current_hp = 0.0
                        current_exists = False
                        current_respawn = None
                        
                        for m_name in known_monsters:
                            # Check if m_name is in the segment
                            if m_name in seg:
                                current_monster = m_name
                                break
                        
                        if current_monster:
                            # Check existence
                            if "不存在" in seg:
                                current_exists = False
                                # Check respawn time
                                # 107秒后刷新 or 1067秒后刷新
                                r_match = re.search(r'(\d+)秒后刷新', seg)
                                if r_match:
                                    current_respawn = int(r_match.group(1))
                            elif "存在" in seg or "血量" in seg: # "存活可见" implies existence
                                current_exists = True
                            
                            # Check Coords
                            c_match = re.search(r'坐标[（\(]([\d\.-]+)，([\d\.-]+)[）\)]', seg)
                            if c_match:
                                current_coord = (float(c_match.group(1)), float(c_match.group(2)))
                            
                            # Check HP
                            hp_match = re.search(r'血量(\d+)%', seg)
                            if hp_match:
                                current_hp = float(hp_match.group(1)) / 100.0
                            elif current_exists:
                                # If exists but no HP specified (e.g. "存在" but no HP info?), assume 100%?
                                # The sample says: "存在血量100%"
                                # If just "存在", assume 1.0
                                current_hp = 1.0
                            
                            # Allow adding even if no coords, for bottom panel display
                            if current_monster:
                                match_state.monsters.append(MonsterStatus(
                                    name=current_monster,
                                    position=current_coord if current_coord else (0.0, 0.0), # Dummy coord if missing
                                    hp_percent=current_hp,
                                    exists=current_exists,
                                    description=seg,
                                    respawn_time=current_respawn
                                ))

        return match_state

    def _parse_hero_line(self, line: str, match_state: MatchState):
        # This is complex due to natural language. Regex is friend.
        # <我方-玩家-廉颇>
        name_match = re.match(r'<([^>]+)>', line)
        if not name_match:
            return
        
        full_name_tag = name_match.group(1)
        parts = full_name_tag.split('-')
        # Handle different length: 我方-玩家名-英雄名 OR 敌方-玩家名-英雄名
        team_str = "blue" if parts[0] == "我方" else "red"
        player_name = parts[1]
        hero_name = parts[-1]

        hero = HeroStatus(
            name=hero_name,
            player_name=player_name,
            team=team_str,
            role="",
            level=1,
            hp_percent=1.0,
            mana_percent=1.0
        )
        
        # Parse Role
        if "是" in line and "路" in line:
             role_match = re.search(r'是(我方|敌方)([^，]+)', line)
             if role_match:
                 hero.role = role_match.group(2)

        # Parse Level
        lvl_match = re.search(r'(\d+)级', line)
        if lvl_match:
            hero.level = int(lvl_match.group(1))
        
        # Parse Dead/Alive
        if "已阵亡" in line:
            hero.is_dead = True
            respawn_match = re.search(r'还有(\d+)秒复活', line)
            if respawn_match:
                hero.respawn_time = int(respawn_match.group(1))
                hero.hp_percent = 0
        else:
             # Parse HP/Mana
             hp_match = re.search(r'血量.*?（(\d+)%）', line)
             if hp_match:
                 hero.hp_percent = int(hp_match.group(1)) / 100.0
             
             mana_match = re.search(r'蓝量(\d+)%', line)
             if mana_match:
                 hero.mana_percent = int(mana_match.group(1)) / 100.0
        
        # Parse Coordinates
        coord_match = re.search(r'坐标[（\(]([\d\.-]+)，([\d\.-]+)[）\)]', line)
        if coord_match:
             hero.position = (float(coord_match.group(1)), float(coord_match.group(2)))
        
        # Parse KDA
        kda_match = re.search(r'击杀：(\d+)，助攻：(\d+)，死亡：(\d+)', line)
        if kda_match:
            hero.kda = (int(kda_match.group(1)), int(kda_match.group(3)), int(kda_match.group(2))) # K D A
        
        # Parse Gold
        gold_match = re.search(r'当前经济：(\d+)', line)
        if gold_match:
            hero.gold = int(gold_match.group(1))
        
        # Parse Items
        items_match = re.search(r'已出装备：([^，。]+)', line)
        # Note: items are listed until next comma/period or end? 
        # Example: 已出装备：红莲斗篷、霸者重装...，剩余金币...
        # Better regex needed
        if "已出装备：" in line:
            try:
                items_part = line.split("已出装备：")[1].split("，")[0]
                hero.items = [i.strip() for i in items_part.split('、')]
            except:
                pass

        # Parse Buffs
        if "暴君buff" in line:
            hero.buffs.append("暴君")
        # Add more buffs if needed

        # Parse Ult
        if "没有大招" in line:
            hero.has_ult = False
        else:
            # Default assume true unless specified? Or assume unknown.
            # Text says "没有大招". If it has ult, maybe it says "大招就绪"?
            # For now assume False if "没有大招", True otherwise? 
            # Or maybe just rely on explicit negative. 
            # Actually, if text doesn't mention it, it's hard to say. 
            # But usually the text generator describes status.
            # "14级，没有大招" -> False.
            hero.has_ult = True 
            if "没有大招" in line:
                hero.has_ult = False

        match_state.heroes.append(hero)

    def _parse_tower_minion_line(self, line: str, match_state: MatchState, static_towers: Dict):
        # Example: 上路：我方上路防御塔被推到上路一塔，坐标（-51.80，21.20），剩余血量31%...
        segments = line.split('；')
        
        # Tower order: Inner to Outer for reconstruction logic?
        # Actually, better logic:
        # We have 3 towers per lane per team.
        # We determine which are alive.
        # "被推到X" means X is the FIRST alive tower from the center (or from outside?).
        # Usually "Pushed to X" implies X is the frontier.
        # If X = T1 (Outer), then T1, T2, High are alive.
        # If X = T2 (Inner), then T1 dead, T2, High alive.
        # If X = High, T1, T2 dead, High alive.
        # If X = Crystal (not tower but location), all towers dead.
        
        towers_map = ["一塔", "二塔", "高地塔"]
        
        for seg in segments:
            # Minions
            # Parsing logic:
            # Each segment describes a tower status AND potentially a threatening minion wave.
            # "我方...防御塔..." segment describes ALLY tower.
            # If this segment has "最近的威胁兵线为...", it means minions are threatening THIS ALLY TOWER.
            # Therefore, these minions belong to the ENEMY (Red).
            
            # "敌方...防御塔..." segment describes ENEMY tower.
            # If this segment has "最近的威胁兵线为...", it means minions are threatening THIS ENEMY TOWER.
            # Therefore, these minions belong to the ALLY (Blue).

            # We need to determine if the segment is about "我方" (Ally/Blue Tower) or "敌方" (Enemy/Red Tower)
            # But be careful, the segment string might contain "我方" in other contexts (like "我方上路一塔").
            
            # Let's look at the tower match first to identify the context of the segment.
            tower_match_for_context = re.search(r'(我方|敌方)([^防御塔]+)防御塔被推到', seg)
            context_team = None # The team who OWNS the tower being described
            if tower_match_for_context:
                context_team = "blue" if tower_match_for_context.group(1) == "我方" else "red"
            
            if "最近的威胁兵线为" in seg:
                # Default logic if we can't find tower context (fallback, though rare)
                minion_team = "red" # Default to enemy minions (threatening us)
                
                if context_team == "blue":
                    # Tower is Blue -> Minions are Red
                    minion_team = "red"
                elif context_team == "red":
                    # Tower is Red -> Minions are Blue
                    minion_team = "blue"
                
                lane = line.split('：')[0].strip()
                
                m_match = re.search(r'最近的威胁兵线为(.*?)，.*?坐标[（\(]([\d\.-]+)，([\d\.-]+)[）\)].*?数量(\d+).*?血量(\d+)%', seg)
                if m_match:
                    match_state.minions.append(MinionStatus(
                        team=minion_team,
                        lane=lane,
                        position=(float(m_match.group(2)), float(m_match.group(3))),
                        count=int(m_match.group(4)),
                        hp_percent=float(m_match.group(5))/100.0,
                        minion_type=m_match.group(1)
                    ))

            # Towers
            tower_match = re.search(r'(我方|敌方)([^防御塔]+)防御塔被推到(.*?)，.*?坐标[（\(]([\d\.-]+)，([\d\.-]+)[）\)].*?剩余血量(\d+)%', seg)
            if tower_match:
                team_str = "blue" if tower_match.group(1) == "我方" else "red"
                lane_str = tower_match.group(2).strip() # "上路"
                current_tower_name = tower_match.group(3).strip() # "上路一塔"
                hp = int(tower_match.group(6)) / 100.0
                
                # Identify the index of the current frontier tower
                frontier_idx = -1
                for i, t in enumerate(towers_map):
                    if t in current_tower_name:
                        frontier_idx = i
                        break
                
                if frontier_idx != -1:
                    # Add this frontier tower with parsed HP
                    # But we need coordinates. The line gives coordinates of this tower.
                    # Use parsed coords for the frontier one.
                    pos = (float(tower_match.group(4)), float(tower_match.group(5)))
                    match_state.towers.append(TowerStatus(
                        team=team_str,
                        lane=lane_str,
                        tower_type=towers_map[frontier_idx],
                        hp_percent=hp,
                        position=pos,
                        is_destroyed=False
                    ))
                    
                    # Add inner towers (those with index > frontier_idx) as 100% HP
                    # Disabled as per user request: only show the outermost (active) tower
                    # for i in range(frontier_idx + 1, len(towers_map)):
                    #      t_type = towers_map[i]
                    #      # Get static coords
                    #      static_pos = static_towers.get((team_str, lane_str, t_type))
                    #      if static_pos:
                    #          match_state.towers.append(TowerStatus(
                    #              team=team_str,
                    #              lane=lane_str,
                    #              tower_type=t_type,
                    #              hp_percent=1.0,
                    #              position=static_pos,
                    #              is_destroyed=False
                    #          ))
                else:
                    # Maybe pushed to Crystal? If so, no towers added.
                    pass

if __name__ == "__main__":
    # Test
    with open("data/sample.txt", "r") as f:
        parser = MatchParser()
        state = parser.parse(f.read())
        print(state)

