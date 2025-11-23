import os
import json
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    from .parser import MatchState, HeroStatus, TowerStatus, MinionStatus
except ImportError:
    from parser import MatchState, HeroStatus, TowerStatus, MinionStatus

class MatchRenderer:
    def __init__(self, assets_dir="assets", scale_factor=2.0):
        self.assets_dir = assets_dir
        self.scale_factor = scale_factor
        
        # Base dimensions
        base_map_size = 800
        self.base_padding_top = 150
        # Set base panel width explicitly (narrower width, e.g. 280)
        self.base_panel_width = 280
        
        # Calculate total base width based on map + 2 * panels
        base_width = base_map_size + 2 * self.base_panel_width
        base_height = 1080 + 100 # Increased height for bottom panel
        
        # Scaled dimensions
        self.width = int(base_width * scale_factor)
        self.height = int(base_height * scale_factor)
        self.map_size = int(base_map_size * scale_factor)
        
        # Load Hero Metadata for Name -> ID mapping
        self.hero_map = {}
        try:
            with open(os.path.join(assets_dir, "heroes.json"), "r", encoding="utf-8") as f:
                heroes = json.load(f)
                for h in heroes:
                    self.hero_map[h['cname']] = h['ename']
        except Exception as e:
            print(f"Warning: Could not load heroes.json: {e}")
            
        # Load Item Metadata
        self.item_map = {} # Name -> ID
        try:
            with open(os.path.join(assets_dir, "items.json"), "r", encoding="utf-8") as f:
                items = json.load(f)
                for i in items:
                    self.item_map[i['item_name']] = i['item_id']
        except Exception as e:
            print(f"Warning: Could not load items.json: {e}")
            
        # Fonts
        self.font_path = None
        
        # 1. Check assets/fonts/ directory
        font_dir = os.path.join(self.assets_dir, "fonts")
        if os.path.exists(font_dir):
            for f in os.listdir(font_dir):
                if f.lower().endswith(('.ttf', '.ttc', '.otf')):
                    self.font_path = os.path.join(font_dir, f)
                    break

        # 2. If not found, check system fonts
        if not self.font_path:
            possible_fonts = [
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "C:\\Windows\\Fonts\\msyh.ttc", # Windows
                "C:\\Windows\\Fonts\\simhei.ttf",
                "simhei.ttf",
                "msyh.ttc"
            ]
            for p in possible_fonts:
                if os.path.exists(p):
                    self.font_path = p
                    break
        
        if not self.font_path:
            print("Warning: No suitable font found. Chinese characters may not display correctly.")

        # Colors
        self.colors = {
            'blue_tower': '#1d4ed8',   # Deeper Blue (700)
            'red_tower': '#b91c1c',    # Deeper Red (700)
            'blue_minion': '#2563eb',  # Blue 600
            'red_minion': '#dc2626',   # Red 600
            'hp_bar': '#16a34a',       # Green 600
            'mana_bar': '#2563eb',     # Blue 600
            'text_white': '#ffffff',
            'text_gold': '#fbbf24',    # Amber 400
            'bg_dark': '#1e1e1e',
            'panel_bg': '#2d2d2d',
            'panel_border': '#444444',
            'ult_active': '#16a34a',
            'ult_inactive': '#555555',
            'border_blue': '#1d4ed8',
            'border_red': '#b91c1c',
            'border_player': '#22c55e',
            'buff_blue': '#3b82f6',
            'buff_red': '#ef4444',
            'buff_tyrant': '#eab308',
            'buff_dragon': '#f59e0b'
        }
        
        # Load Invisible Icon
        self.invisible_icon = None
        try:
            inv_path = os.path.join(self.assets_dir, "invisible.png")
            if os.path.exists(inv_path):
                self.invisible_icon = Image.open(inv_path)
        except Exception as e:
            print(f"Warning: Could not load invisible.png: {e}")

    def s(self, val):
        """Scale a value by the scale factor."""
        return int(val * self.scale_factor)

    def render(self, match_state: MatchState) -> Image.Image:
        # Create canvas
        img = Image.new('RGB', (self.width, self.height), color=self.colors['bg_dark'])
        draw = ImageDraw.Draw(img)
        
        # Calculate Layout
        # Map Center
        map_x = (self.width - self.map_size) // 2
        map_y = self.s(self.base_padding_top)
        self.map_rect = (map_x, map_y, map_x + self.map_size, map_y + self.map_size)
        
        # Draw Base Map
        self._draw_map(img, map_x, map_y)
        
        # Draw Objects on Map
        self._draw_map_elements(img, draw, match_state)
        
        # Draw Side Panels
        self._draw_side_panels(img, draw, match_state)
        
        # Draw Top Bar
        self._draw_top_bar(img, draw, match_state)
        
        # Draw Bottom Panel
        self._draw_bottom_panel(img, draw, match_state)
        
        return img

    def _coord_transform(self, gx, gy):
        # Standard mapping: x:[-60, 60] -> [0, map_size], y:[-60, 60] -> [map_size, 0]
        scale = self.map_size / 120.0
        cx = self.map_rect[0] + (gx + 60) * scale
        cy = self.map_rect[1] + (60 - gy) * scale # Flip Y
        return cx, cy

    def _draw_map(self, img, x, y):
        # Try to load map image
        map_path = os.path.join(self.assets_dir, "map", "map.png")
        if os.path.exists(map_path):
            map_img = Image.open(map_path)
            # High quality resize
            map_img = map_img.resize((self.map_size, self.map_size), resample=Image.LANCZOS)
            img.paste(map_img, (x, y))
        else:
            # Draw vector placeholder
            d = ImageDraw.Draw(img)
            # Background
            d.rectangle((x, y, x + self.map_size, y + self.map_size), fill='#0b0f19', outline='#333')
            # River
            d.line((x, y + self.map_size, x + self.map_size, y), fill='#1c2b3d', width=self.s(40))
            # Lanes (Simple lines)
            w = self.s(10)
            # Top
            d.line((x, y + self.map_size, x, y), fill='#2a2a2a', width=w)
            d.line((x, y, x + self.map_size, y), fill='#2a2a2a', width=w)
            # Bottom
            d.line((x, y + self.map_size, x + self.map_size, y + self.map_size), fill='#2a2a2a', width=w)
            d.line((x + self.map_size, y + self.map_size, x + self.map_size, y), fill='#2a2a2a', width=w)
            # Mid
            d.line((x, y + self.map_size, x + self.map_size, y), fill='#2a2a2a', width=w)

    def _draw_map_elements(self, img, draw, match_state):
        # Store monster coordinates for bottom panel
        self.monster_map_coords = {}

        # Towers
        for tower in match_state.towers:
            cx, cy = self._coord_transform(*tower.position)
            color = self.colors['blue_tower'] if tower.team == "blue" else self.colors['red_tower']
            # Radius increased by 50% (8 -> 12)
            r = self.s(12)
            draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=color, outline='white', width=self.s(1))
            # HP Bar adjusted for new size
            self._draw_bar(draw, cx-self.s(15), cy-self.s(20), self.s(30), self.s(4), tower.hp_percent, color)

        # Minions moved to end


        # Monsters
        for monster in match_state.monsters:
            if not monster.exists:
                continue
                
            cx, cy = self._coord_transform(*monster.position)
            
            # Determine Color/Style based on name
            m_color = '#aaaaaa'
            label = "M"
            if "主宰" in monster.name:
                m_color = '#a855f7' # Purple
                label = "主"
            elif "暴君" in monster.name:
                m_color = '#eab308' # Yellow/Gold
                label = "暴"
            elif "风暴龙王" in monster.name:
                m_color = '#f59e0b' # Orange
                label = "龙"
            elif "蓝buff" in monster.name:
                m_color = '#3b82f6' # Blue
                label = "蓝"
            elif "红buff" in monster.name:
                m_color = '#ef4444' # Red
                label = "红"
            
            # Store coords for overlap check later
            # Use specific keys to distinguish ally/enemy buffs if possible, 
            # but for now store by full name which includes "我方"/"敌方" usually
            self.monster_map_coords[monster.name] = (cx, cy)
            
            # Draw Icon (Circle with Text for now)
            r = self.s(12)
            draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=m_color, outline='white', width=self.s(2))
            
            font_m = self._get_font(self.s(14))
            draw.text((cx, cy), label, font=font_m, anchor="mm", fill="white")
            
            # HP Bar
            self._draw_bar(draw, cx-self.s(12), cy-self.s(18), self.s(24), self.s(4), monster.hp_percent, self.colors['hp_bar'])

        # Heroes
        # We draw heroes last so they are on top
        # Need to store hero screen coords for connecting lines
        self.hero_map_coords = {} # hero_name -> (x, y)
        
        for hero in match_state.heroes:
            if hero.position:
                cx, cy = self._coord_transform(*hero.position)
                self.hero_map_coords[hero.name] = (cx, cy)
                
                # Load Icon
                # Icon size increased by 50% (32 -> 48)
                icon_size = self.s(48)
                icon = self._get_hero_icon(hero.name)
                if icon:
                    icon = icon.resize((icon_size, icon_size), resample=Image.LANCZOS)
                    # Create circular mask
                    mask = Image.new('L', (icon_size, icon_size), 0)
                    draw_mask = ImageDraw.Draw(mask)
                    draw_mask.ellipse((0, 0, icon_size, icon_size), fill=255)
                    
                    # Border color
                    if "玩家" in hero.player_name:
                        border_color = self.colors['border_player']
                    else:
                        border_color = self.colors['border_blue'] if hero.team == "blue" else self.colors['border_red']
                    
                    # Draw border circle
                    border_w = self.s(3) # Slightly thicker border
                    draw.ellipse((cx-icon_size//2-border_w, cy-icon_size//2-border_w, 
                                  cx+icon_size//2+border_w, cy+icon_size//2+border_w), fill=border_color)
                    img.paste(icon, (int(cx-icon_size//2), int(cy-icon_size//2)), mask)
                else:
                    r = self.s(15) # Adjusted placeholder size
                    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill='gray')
                
                # Name & HP
                # Draw player name above HP bar
                font_name_map = self._get_font(self.s(18))
                # HP bar top is at cy - 18 (offset_y_hp)
                # We draw slightly above that. With larger icon (48/2 = 24 radius), bar needs to be lower?
                # Previous icon r=16. Bar was at cy-18.
                # New icon r=24. Bar at cy-18 overlaps icon.
                # Need to move bars down or icon up?
                # Let's move bars below icon? Or keep above?
                # If above: cy - 24 - padding.
                # If below: cy + 24 + padding.
                # Original code: cy-18 for HP bar.
                # Let's push bars down below icon to avoid clutter? Or just further up?
                # User said "位于血条蓝条上放".
                # Let's move bars down to be under the larger icon, or keep them relative to center but avoid overlap.
                # Icon covers cy-24 to cy+24.
                # So bars should be at cy+28?
                # Let's try placing bars UNDER the icon for better visibility with large icons.
                
                offset_y_hp = self.s(28)
                offset_y_mana = self.s(32)
                
                # Name above icon?
                # draw.text((cx, cy - self.s(35)), hero.player_name, ...)
                
                # WAIT, user instruction: "在英雄图标的上方（位于血条蓝条上放））也写上使用英雄的玩家名"
                # This implies order: Name -> HP/Mana -> Icon? Or Icon -> Name -> HP/Mana?
                # Usually: Name \n HP Bar \n Icon OR Icon \n HP Bar.
                # Let's stick to: Name -> HP Bar -> Icon (if bars are on top)
                # But if icon is big, bars on top might obscure map behind?
                # Let's put bars BELOW icon.
                # Icon center (cx, cy). Radius 24.
                # Bar starts at cy + 26.
                # Name starts at cy - 36?
                
                # Let's try keeping bars BELOW icon.
                
                self._draw_bar(draw, cx-self.s(15), cy+offset_y_hp, self.s(30), self.s(4), hero.hp_percent, self.colors['hp_bar'])
                self._draw_bar(draw, cx-self.s(15), cy+offset_y_mana, self.s(30), self.s(2), hero.mana_percent, self.colors['mana_bar'])
                
                # Name above icon
                draw.text((cx, cy - self.s(32)), hero.player_name, font=font_name_map, anchor="md", fill=self.colors['text_white'], stroke_width=self.s(1), stroke_fill='black')

        # Minions
        for minion in match_state.minions:
            cx, cy = self._coord_transform(*minion.position)
            color = self.colors['blue_minion'] if minion.team == "blue" else self.colors['red_minion']
            r = self.s(6) # 2x size (was 3)
            draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=color)
            
            # Draw Count and HP
            font_minion = self._get_font(self.s(12))
            # e.g. "3\n50%"
            info_txt = f"{minion.count} | {int(minion.hp_percent * 100)}%"
            draw.text((cx, cy - self.s(10)), info_txt, font=font_minion, anchor="mb", fill="white", stroke_width=self.s(1), stroke_fill='black')

    def _draw_bar(self, draw, x, y, w, h, pct, color):
        draw.rectangle((x, y, x+w, y+h), fill='#333')
        if pct > 0:
            draw.rectangle((x, y, x+int(w*pct), y+h), fill=color)

    def _draw_side_panels(self, img, draw, match_state):
        # Split heroes by team
        blue_heroes = [h for h in match_state.heroes if h.team == "blue"]
        red_heroes = [h for h in match_state.heroes if h.team == "red"]
        
        # Use the full available space for the panel, which is now tight
        panel_width = (self.width - self.map_size) // 2
        
        start_y = self.s(self.base_padding_top)
        spacing = self.s(150)
        
        # Left Panel (Blue)
        for i, hero in enumerate(blue_heroes):
            y = start_y + i * spacing
            self._draw_hero_card(img, draw, hero, self.s(20), y, panel_width - self.s(40), "left")
            
        # Right Panel (Red)
        for i, hero in enumerate(red_heroes):
            y = start_y + i * spacing
            # Anchor to right edge: x = width - panel_width + margin
            self._draw_hero_card(img, draw, hero, self.width - panel_width + self.s(20), y, panel_width - self.s(40), "right")

    def _draw_dashed_line(self, draw, start, end, fill='white', width=1, dash_length=10, gap_length=5):
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1
        distance = math.sqrt(dx**2 + dy**2)
        if distance == 0:
            return
            
        angle = math.atan2(dy, dx)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        
        current_dist = 0
        while current_dist < distance:
            # Draw segment
            seg_len = min(dash_length, distance - current_dist)
            ex = x1 + (current_dist + seg_len) * cos_a
            ey = y1 + (current_dist + seg_len) * sin_a
            sx = x1 + current_dist * cos_a
            sy = y1 + current_dist * sin_a
            
            draw.line((sx, sy, ex, ey), fill=fill, width=width)
            current_dist += dash_length + gap_length

    def _check_overlap(self, pos1, pos2, radius):
        """Check if two positions are overlapping within a certain radius."""
        x1, y1 = pos1
        x2, y2 = pos2
        dist = math.sqrt((x1 - x2)**2 + (y1 - y2)**2)
        return dist < (radius * 2) # Simple collision check

    def _draw_hero_card(self, img, draw, hero, x, y, w, align):
        # Background
        h = self.s(120)
        draw.rectangle((x, y, x+w, y+h), fill=self.colors['panel_bg'], outline=self.colors['panel_border'])
        
        # Avatar
        icon_size = self.s(64)
        icon = self._get_hero_icon(hero.name)
        if icon:
            icon = icon.resize((icon_size, icon_size), resample=Image.LANCZOS)
            if hero.is_dead:
                icon = icon.convert('L') # Grayscale
            img.paste(icon, (x+self.s(10), y+self.s(10)))
            
            # Overlay Invisible Icon
            if not hero.is_visible and self.invisible_icon:
                inv_icon = self.invisible_icon.resize((icon_size, icon_size), resample=Image.LANCZOS)
                if inv_icon.mode != 'RGBA':
                    inv_icon = inv_icon.convert('RGBA')
                
                # Adjust alpha for semi-transparency
                r, g, b, a = inv_icon.split()
                a = a.point(lambda i: i * 0.8) # 80% opacity
                inv_icon.putalpha(a)
                
                img.paste(inv_icon, (x+self.s(10), y+self.s(10)), inv_icon)
            
        # Name
        font_name = self._get_font(self.s(16))
        draw.text((x+self.s(80), y+self.s(10)), f"{hero.name} ({hero.player_name})", font=font_name, fill=self.colors['text_white'])
        
        # HP/Mana Info
        font_small = self._get_font(self.s(12))
        hp_pct_str = f"{int(hero.hp_percent * 100)}%"
        mana_pct_str = f"{int(hero.mana_percent * 100)}%"
        info_text = f"HP: {hp_pct_str}   MP: {mana_pct_str}"
        draw.text((x+self.s(80), y+self.s(32)), info_text, font=font_small, fill="#cccccc")

        # Gold/KDA
        draw.text((x+self.s(80), y+self.s(50)), f"Gold: {hero.gold}  KDA: {hero.kda[0]}/{hero.kda[1]}/{hero.kda[2]}", font=font_small, fill="#aaaaaa")
        
        # Status Icons (Ult, Buffs)
        status_x = x + self.s(80)
        status_y = y + self.s(68)
        
        # Ult
        ult_color = self.colors['ult_active'] if hero.has_ult else self.colors['ult_inactive']
        ult_size = self.s(10)
        draw.ellipse((status_x, status_y, status_x+ult_size, status_y+ult_size), fill=ult_color)
        draw.text((status_x+self.s(12), status_y-self.s(2)), "Ult", font=font_small, fill="white")

        # Buffs
        current_status_x = status_x + self.s(35)
        buff_size = self.s(10)
        
        for buff in hero.buffs:
            b_color = 'white'
            label = "?"
            if "蓝" in buff:
                b_color = self.colors['buff_blue']
                label = "蓝"
            elif "红" in buff:
                b_color = self.colors['buff_red']
                label = "红"
            elif "暴君" in buff:
                b_color = self.colors['buff_tyrant']
                label = "暴"
            elif "风暴" in buff or "龙" in buff:
                b_color = self.colors['buff_dragon']
                label = "龙"
            
            # Draw Circle
            draw.ellipse((current_status_x, status_y, current_status_x + buff_size, status_y + buff_size), fill=b_color)
            
            # Draw Text
            draw.text((current_status_x + buff_size + self.s(4), status_y - self.s(2)), label, font=font_small, fill=b_color)
            
            # Advance
            current_status_x += self.s(28)
        
        # Items
        item_x = x + self.s(10)
        item_y = y + self.s(80)
        # Reduced item size to fit narrower card (was 30/35)
        item_size = self.s(22)
        item_spacing = self.s(26)
        for item_name in hero.items:
            item_icon = self._get_item_icon(item_name)
            if item_icon:
                item_icon = item_icon.resize((item_size, item_size), resample=Image.LANCZOS)
                img.paste(item_icon, (item_x, item_y))
                item_x += item_spacing

        # Connecting Line logic
        # Connect card center to map position
        card_cy = y + h // 2
        card_cx = x + w if align == "left" else x
        
        # Only draw if overlapping with another hero on map
        if hero.name in self.hero_map_coords:
            map_cx, map_cy = self.hero_map_coords[hero.name]
            
            is_overlapping = False
            current_pos = (map_cx, map_cy)
            icon_radius = self.s(24) # Half of 48
            
            for other_name, other_pos in self.hero_map_coords.items():
                if other_name != hero.name:
                    if self._check_overlap(current_pos, other_pos, icon_radius):
                        is_overlapping = True
                        break
            
            # Always draw for player? Or strictly only if overlapping?
            # User said "为了避免连线的视觉干扰，仅在英雄图标与其他英雄图标产生重叠时，才增加连线"
            # Assuming this applies to everyone including player.
            
            if is_overlapping:
                # Line Color: Green for Player, else Team Color
                if "玩家" in hero.player_name:
                    line_color = self.colors['border_player'] # Green
                else:
                    line_color = self.colors['border_blue'] if hero.team == "blue" else self.colors['border_red']
                
                # Thinner line (50% reduction from previous s(3) -> s(1.5) approx s(1) or s(2))
                # Let's use s(1.5) rounded
                width = max(1, int(self.s(1.5)))
                
                self._draw_dashed_line(draw, (card_cx, card_cy), (map_cx, map_cy), fill=line_color, width=width, dash_length=self.s(10), gap_length=self.s(8))

    def _draw_top_bar(self, img, draw, match_state):
        # Time
        font_large = self._get_font(self.s(32))
        cx = self.width // 2
        draw.text((cx, self.s(40)), match_state.time_str, font=font_large, anchor="mm", fill="white")
        
        # Scores
        font_score = self._get_font(self.s(40))
        offset_score = self.s(150)
        draw.text((cx - offset_score, self.s(40)), str(match_state.blue_kills), font=font_score, anchor="mm", fill=self.colors['blue_tower'])
        draw.text((cx + offset_score, self.s(40)), str(match_state.red_kills), font=font_score, anchor="mm", fill=self.colors['red_tower'])
        
        # Gold (Restored)
        font_gold = self._get_font(self.s(20))
        offset_gold_y = self.s(80)
        draw.text((cx - offset_score, offset_gold_y), f"💰 {match_state.blue_gold}", font=font_gold, anchor="mm", fill=self.colors['text_gold'])
        draw.text((cx + offset_score, offset_gold_y), f"💰 {match_state.red_gold}", font=font_gold, anchor="mm", fill=self.colors['text_gold'])

        # Dead Heroes List
        font_dead = self._get_font(self.s(16))
        # Adjusted offset to be below Gold
        offset_dead_y = self.s(110)
        
        blue_dead = [f"{h.name}" + (f"({h.player_name})" if "玩家" in h.player_name else "") for h in match_state.heroes if h.team == "blue" and h.is_dead]
        red_dead = [f"{h.name}" + (f"({h.player_name})" if "玩家" in h.player_name else "") for h in match_state.heroes if h.team == "red" and h.is_dead]
        
        if blue_dead:
            dead_text = "💀 " + " ".join(blue_dead)
            draw.text((cx - offset_score, offset_dead_y), dead_text, font=font_dead, anchor="mm", fill="#9ca3af")
            
        if red_dead:
            dead_text = "💀 " + " ".join(red_dead)
            draw.text((cx + offset_score, offset_dead_y), dead_text, font=font_dead, anchor="mm", fill="#9ca3af")

    def _draw_bottom_panel(self, img, draw, match_state):
        # Panel Area
        panel_h = self.height - (self.map_rect[3] + self.s(40)) # approx bottom area
        # But we extended height, so let's use fixed area at bottom
        panel_y = self.height - self.s(180) # Bottom 180px
        panel_h = self.s(180)
        
        # Background
        # draw.rectangle((0, panel_y, self.width, self.height), fill=self.colors['panel_bg'])
        
        # Order: Ally Blue, Ally Red, Overlord, Storm Dragon, Tyrant, Enemy Red, Enemy Blue
        monster_order = [
            ("我方蓝buff", "蓝Buff", self.colors['blue_minion']),
            ("我方红buff", "红Buff", self.colors['red_minion']),
            ("主宰", "主宰", '#a855f7'),
            ("风暴龙王", "风暴龙王", '#f59e0b'),
            ("暴君", "暴君", '#eab308'),
            ("敌方红buff", "红Buff", self.colors['red_minion']),
            ("敌方蓝buff", "蓝Buff", self.colors['blue_minion'])
        ]
        
        # Layout
        count = len(monster_order)
        item_width = self.width // count
        
        font_name = self._get_font(self.s(16))
        font_status = self._get_font(self.s(14))
        
        for i, (key, label, color) in enumerate(monster_order):
            cx = i * item_width + item_width // 2
            cy = panel_y + panel_h // 2
            
            # Find status
            status = None
            for m in match_state.monsters:
                # Fuzzy matching logic
                # match_state.monsters contains parsed names like "主宰", "暴君"
                # key comes from monster_order: "主宰", "暴君", "我方蓝buff" etc.
                
                if key in m.name or m.name in key:
                    status = m
                    break
            
            # Draw Icon
            r = self.s(20)
            
            # Draw Slot Background
            # draw.rectangle((i*item_width + self.s(10), panel_y + self.s(20), (i+1)*item_width - self.s(10), self.height - self.s(20)), outline='#444')
            
            if status:
                # Exists/Visible
                if status.exists:
                    fill_color = color
                    status_text = f"HP: {int(status.hp_percent * 100)}%"
                    alpha = 255
                else:
                    fill_color = '#555' # Dead/Respawning
                    # If exists is False, it means we parsed it as "不存在" or similar.
                    if status.respawn_time:
                        status_text = f"{status.respawn_time}s后刷新"
                    else:
                        status_text = "不存在"
                    alpha = 100
                
                draw.ellipse((cx-r, cy-r-self.s(20), cx+r, cy+r-self.s(20)), fill=fill_color, outline='white', width=self.s(2))
                draw.text((cx, cy - self.s(20)), label[0], font=font_name, anchor="mm", fill="white")
                
                # Name
                draw.text((cx, cy + self.s(20)), label, font=font_name, anchor="mm", fill="white")
                
                # Status Text
                draw.text((cx, cy + self.s(45)), status_text, font=font_status, anchor="mm", fill="#ccc")
                
                # Connection Line Logic
                # "如果对应野怪可见，并且在核心区域的图标与其他英雄图标重叠"
                if status.exists and status.name in self.monster_map_coords:
                    map_pos = self.monster_map_coords[status.name]
                    
                    # Check overlap with heroes
                    is_overlapping = False
                    icon_radius = self.s(15) # Monster icon radius approx
                    
                    for h_name, h_pos in self.hero_map_coords.items():
                        if self._check_overlap(map_pos, h_pos, icon_radius + self.s(16)): # hero radius approx 16-24
                            is_overlapping = True
                            break
                    
                    if is_overlapping:
                        # Draw line from Card (cx, cy-r-20) to Map Pos
                        # Start from top of card icon
                        start_pos = (cx, cy - r - self.s(20))
                        self._draw_dashed_line(draw, start_pos, map_pos, fill='#888888', width=self.s(2), dash_length=self.s(8))
                        
            else:
                # Unknown / Not visible
                draw.ellipse((cx-r, cy-r-self.s(20), cx+r, cy+r-self.s(20)), outline='#444', width=self.s(2))
                draw.text((cx, cy - self.s(20)), "?", font=font_name, anchor="mm", fill="#555")
                draw.text((cx, cy + self.s(20)), label, font=font_name, anchor="mm", fill="#555")
                draw.text((cx, cy + self.s(45)), "未知", font=font_status, anchor="mm", fill="#555")

    def _get_hero_icon(self, name):
        ename = self.hero_map.get(name)
        if ename:
            path = os.path.join(self.assets_dir, "heroes", f"{ename}.jpg")
            if os.path.exists(path):
                return Image.open(path)
        return None

    def _get_item_icon(self, name):
        iid = self.item_map.get(name)
        if iid:
            path = os.path.join(self.assets_dir, "items", f"{iid}.jpg")
            if os.path.exists(path):
                return Image.open(path)
        return None

    def _get_font(self, size):
        if self.font_path:
            return ImageFont.truetype(self.font_path, size)
        return ImageFont.load_default()
