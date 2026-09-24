"""Generate high-resolution pixel-art animated GIFs of working ants in the colony for 4 army tiers.

Resolution: 240x88 (Crisp, detailed fine-pixel underground ant colony).
Usage:  python scripts/gen_colony_gifs.py
"""

from __future__ import annotations

import math
import os
import struct

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "img")

# 24-color rich subterranean palette
PALETTE = [
    (18, 14, 12),     # 0: Deep cavern background (#120e0c)
    (34, 24, 18),     # 1: Dark soil (#221812)
    (58, 40, 28),     # 2: Medium soil (#3a281c)
    (86, 60, 40),     # 3: Light soil / rock (#563c28)
    (115, 82, 54),    # 4: Earth highlight / root (#735236)
    (38, 28, 20),     # 5: Tunnel floor / path (#261c14)
    (10, 10, 10),     # 6: Ant body black (#0a0a0a)
    (35, 28, 24),     # 7: Ant body shadow (#231c18)
    (232, 163, 61),   # 8: Amber highlight (#e8a33d)
    (255, 212, 100),  # 9: Bright gold / Crown (#ffd464)
    (124, 191, 66),   # 10: Fungus leaf green (#7cbf42)
    (74, 138, 38),    # 11: Dark foliage green (#4a8a26)
    (63, 151, 214),   # 12: Water pool blue (#3f97d6)
    (121, 199, 239),  # 13: Water sparkle cyan (#79c7ef)
    (216, 242, 252),  # 14: Water shine / Wing (#d8f2fc)
    (194, 58, 34),    # 15: Major / Soldier reddish (#c23a22)
    (232, 106, 82),   # 16: Red carapace highlight (#e86a52)
    (245, 240, 230),  # 17: Ant egg / Larva white (#f5f0e6)
    (200, 185, 165),  # 18: Egg shadow (#c8b9a5)
    (140, 105, 75),   # 19: Wood / branch (#8c694b)
    (240, 195, 90),   # 20: Golden seed / grain (#f0c35a)
    (255, 235, 160),  # 21: Honeydew glow (#ffeba0)
    (60, 42, 70),     # 22: Deep crystal mineral (#3c2a46)
    (48, 88, 32),     # 23: Top grass shadow (#305820)
]


def write_gif(
    filename: str,
    width: int,
    height: int,
    frames: list[list[int]],
    delays: list[int],
    palette: list[tuple[int, int, int]],
) -> None:
    num_colors = len(palette)
    color_bits = max(2, (num_colors - 1).bit_length())
    color_table_size = 1 << color_bits
    padded_palette = list(palette) + [(0, 0, 0)] * (color_table_size - len(palette))

    with open(filename, "wb") as f:
        f.write(b"GIF89a")
        f.write(
            struct.pack(
                "<HHBBB",
                width,
                height,
                0x80 | (color_bits - 1) << 4 | (color_bits - 1),
                0,
                0,
            )
        )
        f.writelines(struct.pack("BBB", r, g, b) for r, g, b in padded_palette)
        # Netscape Loop Extension (infinite loop)
        f.write(b"\x21\xFF\x0B\x4E\x45\x54\x53\x43\x41\x50\x45\x32\x2E\x30\x03\x01\x00\x00\x00")

        for frame_data, delay in zip(frames, delays, strict=False):
            # Graphic Control Extension
            f.write(struct.pack("<BBBBHBB", 0x21, 0xF9, 0x04, 0x00, delay, 0, 0))
            # Image Descriptor
            f.write(struct.pack("<BHHHHB", 0x2C, 0, 0, width, height, 0x00))

            min_code_size = max(2, color_bits)
            f.write(struct.pack("B", min_code_size))

            clear_code = 1 << min_code_size
            end_code = clear_code + 1

            cur_code_size = min_code_size + 1
            dict_size = end_code + 1
            max_code = 1 << cur_code_size

            code_table = {bytes([i]): i for i in range(clear_code)}
            bits = []

            bits.append((clear_code, cur_code_size))
            curr = b""
            for byte in frame_data:
                b_byte = bytes([byte])
                test = curr + b_byte
                if test in code_table:
                    curr = test
                else:
                    bits.append((code_table[curr], cur_code_size))
                    if dict_size < 4096:
                        code_table[test] = dict_size
                        dict_size += 1
                        if dict_size > max_code and cur_code_size < 12:
                            cur_code_size += 1
                            max_code = 1 << cur_code_size
                    else:
                        bits.append((clear_code, cur_code_size))
                        code_table = {bytes([i]): i for i in range(clear_code)}
                        dict_size = end_code + 1
                        cur_code_size = min_code_size + 1
                        max_code = 1 << cur_code_size
                    curr = b_byte
            if curr:
                bits.append((code_table[curr], cur_code_size))
            bits.append((end_code, cur_code_size))

            raw_bytes = bytearray()
            acc = 0
            acc_bits = 0
            for code, n_bits in bits:
                acc |= code << acc_bits
                acc_bits += n_bits
                while acc_bits >= 8:
                    raw_bytes.append(acc & 0xFF)
                    acc >>= 8
                    acc_bits -= 8
            if acc_bits > 0:
                raw_bytes.append(acc & 0xFF)

            idx = 0
            while idx < len(raw_bytes):
                chunk = raw_bytes[idx : idx + 254]
                f.write(struct.pack("B", len(chunk)))
                f.write(chunk)
                idx += len(chunk)
            f.write(b"\x00")

        f.write(b"\x3B")


class Canvas:
    def __init__(self, w: int, h: int):
        self.w = w
        self.h = h
        self.grid = [0] * (w * h)

    def set_px(self, x: int, y: int, color_idx: int):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.grid[y * self.w + x] = color_idx

    def rect(self, x0: int, y0: int, x1: int, y1: int, color_idx: int):
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                self.grid[y * self.w + x] = color_idx

    def draw_soil_background(self, frame_idx: int = 0):
        # 1. Base Underground Earth
        self.rect(0, 0, self.w - 1, self.h - 1, 1)

        # 2. Organic Strata textures
        for y in range(self.h):
            for x in range(self.w):
                h_val = (x * 13 + y * 29 + (x ^ y)) % 101
                if h_val < 6:
                    self.set_px(x, y, 2)
                elif h_val < 9:
                    self.set_px(x, y, 3)
                elif h_val == 42:
                    self.set_px(x, y, 4)
                elif h_val == 99 and y > 30:
                    self.set_px(x, y, 22)  # tiny mineral purple sparkle

        # 3. Surface ground line (Y: 0 to 6)
        self.rect(0, 0, self.w - 1, 2, 11)  # dark grass
        for x in range(self.w):
            if x % 3 == 0:
                self.set_px(x, 0, 10)  # grass blade green
            if (x * 7) % 11 == 0:
                self.set_px(x, 3, 3)  # pebble

        # 4. TUNNELS & CAVERNS ARCHITECTURE
        # Upper Main Highway (Y: 10 to 24)
        self.rect(0, 10, self.w - 1, 23, 0)
        self.rect(0, 24, self.w - 1, 24, 5)  # floor path

        # Surface Entrance Shaft (X: 110 to 130, Y: 0 to 12)
        self.rect(112, 0, 128, 12, 0)

        # Central Grand Queen Chamber (X: 74 to 166, Y: 28 to 54)
        self.rect(74, 28, 166, 53, 0)
        self.rect(74, 54, 166, 54, 5)  # royal floor

        # Left Chamber: Fungus Garden (X: 0 to 62, Y: 32 to 54)
        self.rect(0, 32, 62, 53, 0)
        self.rect(0, 54, 62, 54, 5)

        # Right Chamber: Water Spring Cavern (X: 178 to 239, Y: 32 to 54)
        self.rect(178, 32, 239, 53, 0)
        self.rect(178, 54, 239, 54, 5)

        # Lower Defense Corridor (Y: 62 to 78)
        self.rect(0, 62, self.w - 1, 77, 0)
        self.rect(0, 78, self.w - 1, 78, 5)  # floor

        # Connecting Shafts
        self.rect(20, 24, 32, 62, 0)  # Left shaft
        self.rect(208, 24, 220, 62, 0)  # Right shaft
        self.rect(114, 54, 126, 62, 0)  # Center shaft

        # 5. Hanging Roots from ceilings
        for rx, rh in [
            (14, 6),
            (45, 8),
            (70, 5),
            (95, 7),
            (145, 6),
            (170, 9),
            (195, 7),
            (230, 8),
            (35, 6),
            (85, 7),
            (155, 6),
        ]:
            for i in range(rh):
                self.set_px(rx + (1 if (i % 2 == 1) else 0), 10 + i, 4)
                if i == rh - 1:
                    self.set_px(rx, 10 + i, 19)

        # 6. Fungus Garden Details (Left Room)
        # Tiered fungus stalks and bioluminescent green caps
        fungus_nodes = [
            (8, 51, 10),
            (18, 48, 10),
            (28, 52, 10),
            (38, 47, 10),
            (48, 50, 10),
            (56, 52, 10),
        ]
        for fx, fy, c in fungus_nodes:
            # Stalk
            self.rect(fx, fy, fx + 1, 53, 19)
            # Cap
            self.rect(fx - 2, fy - 2, fx + 3, fy - 1, c)
            self.set_px(fx - 1, fy - 3, 10)
            self.set_px(fx + 1, fy - 3, 14)  # spore sparkle
            if (frame_idx + fx) % 4 == 0:
                self.set_px(fx, fy - 4, 14)  # floating spore

        # 7. Water Spring Details (Right Room)
        # Subterranean glowing blue pool (X: 184 to 234, Y: 50 to 53)
        self.rect(184, 50, 234, 53, 12)
        for wx in range(186, 233, 2):
            self.set_px(wx + (frame_idx % 2), 50, 13)
        # Stalactite water drips
        self.rect(205, 32, 207, 37, 3)
        self.set_px(206, 38, 14)
        # Falling droplet animation
        drip_y = 39 + ((frame_idx * 3) % 11)
        if drip_y < 50:
            self.set_px(206, drip_y, 13)

        # 8. Royal Queen Dais & Egg Nursery (Middle Room)
        # Egg / Brood clusters
        for ex, ey in [
            (80, 52),
            (83, 53),
            (82, 51),
            (86, 52),
            (89, 53),
            (150, 52),
            (153, 53),
            (152, 51),
            (157, 52),
            (160, 53),
        ]:
            self.rect(ex, ey, ex + 1, ey + 1, 17)
            self.set_px(ex + 1, ey + 1, 18)

        # Queen Throne Carpet / Cushion (X: 108 to 132, Y: 51 to 53)
        self.rect(108, 52, 132, 53, 8)
        self.rect(110, 53, 130, 53, 9)

        # Queen Ant (Center: X: 112 to 128, Y: 42 to 51)
        self.draw_queen(120, 51, frame_idx)

    def draw_queen(self, cx: int, cy: int, frame_idx: int):
        # Grand Queen Ant (Majestic crowned queen facing right)
        breath = 1 if (frame_idx % 4 in (1, 2)) else 0

        # Massive Abdomen (stripes of royal amber & chitin)
        self.rect(cx - 10, cy - 8 + breath, cx - 3, cy - 1, 6)
        self.rect(cx - 9, cy - 7 + breath, cx - 4, cy - 2, 8)
        self.rect(cx - 7, cy - 6 + breath, cx - 5, cy - 3, 9)

        # Petiole & Thorax
        self.rect(cx - 2, cy - 5, cx + 2, cy - 2, 6)
        self.set_px(cx, cy - 4, 8)

        # Head & Mandibles
        self.rect(cx + 3, cy - 6, cx + 6, cy - 3, 6)
        self.set_px(cx + 4, cy - 5, 9)  # eye
        self.set_px(cx + 7, cy - 4, 8)  # jaw
        self.set_px(cx + 7, cy - 3, 6)

        # Golden Crown on Queen's head
        self.set_px(cx + 3, cy - 7, 9)
        self.set_px(cx + 5, cy - 7, 9)
        self.set_px(cx + 4, cy - 8, 9)

        # Antennae twitching
        ant_y = cy - 7 - (1 if (frame_idx % 6 < 3) else 0)
        self.set_px(cx + 6, ant_y, 8)
        self.set_px(cx + 7, ant_y - 1, 8)

        # Queen Legs
        for lx in [cx - 2, cx, cx + 2]:
            self.set_px(lx, cy - 1, 6)
            self.set_px(lx + (1 if lx > cx else -1), cy, 6)

    def draw_worker_ant(
        self,
        x: int,
        y: int,
        facing_right: bool,
        carrying_type: str = "none",
        leg_frame: int = 0,
    ):
        """Crisp, high-detail 7x4 worker ant with animated legs and cargo."""
        dir_mult = 1 if facing_right else -1

        # Body coordinates
        # Abdomen (3x3 oval)
        ab_x = x - (3 * dir_mult)
        self.rect(min(x - dir_mult, ab_x), y - 3, max(x - dir_mult, ab_x), y - 1, 6)
        self.set_px(min(x - dir_mult, ab_x) + 1, y - 2, 7)

        # Thorax (2x2)
        self.rect(min(x, x + dir_mult), y - 2, max(x, x + dir_mult), y - 1, 6)
        self.set_px(x, y - 2, 8)

        # Head (2x2) & Mandibles
        hx = x + (2 * dir_mult)
        self.rect(min(hx, hx + dir_mult), y - 3, max(hx, hx + dir_mult), y - 2, 6)
        self.set_px(hx, y - 3, 8)  # Eye / highlight

        # Antenna
        self.set_px(hx + dir_mult, y - 4, 6)

        # 3 Pairs of Legs (articulated stepping)
        step = leg_frame % 2
        l1_off = 1 if step == 0 else -1
        l2_off = -1 if step == 0 else 1

        self.set_px(x - dir_mult + l1_off, y, 6)
        self.set_px(x, y, 6)
        self.set_px(x + dir_mult + l2_off, y, 6)

        # Carried items
        if carrying_type == "food":
            # Green leaf / fungus chunk
            cx = hx + (2 * dir_mult)
            self.rect(min(cx, cx + dir_mult), y - 5, max(cx, cx + dir_mult), y - 4, 10)
            self.set_px(cx, y - 6, 11)
        elif carrying_type == "water":
            # Shimmering blue water droplet
            cx = hx + (2 * dir_mult)
            self.rect(min(cx, cx + dir_mult), y - 5, max(cx, cx + dir_mult), y - 4, 12)
            self.set_px(cx, y - 5, 14)
        elif carrying_type == "seed":
            # Golden grain
            cx = hx + (2 * dir_mult)
            self.rect(min(cx, cx + dir_mult), y - 5, max(cx, cx + dir_mult), y - 4, 20)
            self.set_px(cx, y - 5, 21)
        elif carrying_type == "egg":
            # White ant larva
            cx = hx + (2 * dir_mult)
            self.rect(min(cx, cx + dir_mult), y - 4, max(cx, cx + dir_mult), y - 3, 17)

    def draw_soldier_ant(self, x: int, y: int, facing_right: bool, leg_frame: int = 0):
        """Powerful 11x6 armored soldier ant with formidable biting jaws."""
        dir_mult = 1 if facing_right else -1

        # Armored Abdomen (4x4)
        ab_x = x - (5 * dir_mult)
        self.rect(min(x - (2 * dir_mult), ab_x), y - 4, max(x - (2 * dir_mult), ab_x), y - 1, 6)
        self.rect(min(x - (2 * dir_mult), ab_x) + 1, y - 3, max(x - (2 * dir_mult), ab_x) - 1, y - 2, 15)

        # Spiky Thorax (3x3)
        self.rect(min(x - dir_mult, x + dir_mult), y - 3, max(x - dir_mult, x + dir_mult), y - 1, 6)
        self.set_px(x, y - 4, 15)  # Thorax spine

        # Massive Head with heavy jaws (4x4)
        hx = x + (3 * dir_mult)
        self.rect(min(hx, hx + (2 * dir_mult)), y - 4, max(hx, hx + (2 * dir_mult)), y - 1, 6)
        self.set_px(hx + dir_mult, y - 3, 8)  # Eye

        # Heavy Mandibles (Red-hot razor jaws)
        jx = hx + (3 * dir_mult)
        self.set_px(jx, y - 4, 15)
        self.set_px(jx + dir_mult, y - 3, 16)
        self.set_px(jx, y - 2, 15)
        self.set_px(jx + dir_mult, y - 1, 16)

        # Antennae
        self.set_px(hx + dir_mult, y - 5, 6)

        # Heavy Legs
        step = leg_frame % 2
        for lx, off in [(-2, 1 if step else -1), (0, 0), (2, -1 if step else 1)]:
            self.set_px(x + (lx * dir_mult) + off, y, 6)

    def draw_major_ant(self, x: int, y: int, facing_right: bool, leg_frame: int = 0):
        """Towering 16x9 Elite Major Ant - heavy fortress defender."""
        dir_mult = 1 if facing_right else -1

        # Huge Spiked Abdomen
        ab_x = x - (7 * dir_mult)
        self.rect(min(x - (2 * dir_mult), ab_x), y - 7, max(x - (2 * dir_mult), ab_x), y - 1, 6)
        self.rect(min(x - (3 * dir_mult), ab_x + dir_mult), y - 6, max(x - (3 * dir_mult), ab_x + dir_mult), y - 2, 15)
        self.set_px(ab_x + (2 * dir_mult), y - 8, 16)  # Carapace dorsal spike

        # Armored Thorax
        self.rect(min(x - dir_mult, x + (2 * dir_mult)), y - 5, max(x - dir_mult, x + (2 * dir_mult)), y - 1, 6)
        self.set_px(x, y - 6, 16)
        self.set_px(x + dir_mult, y - 6, 15)

        # Colossal Head (5x5)
        hx = x + (4 * dir_mult)
        self.rect(min(hx, hx + (3 * dir_mult)), y - 6, max(hx, hx + (3 * dir_mult)), y - 1, 6)
        self.rect(min(hx + dir_mult, hx + (2 * dir_mult)), y - 5, max(hx + dir_mult, hx + (2 * dir_mult)), y - 2, 15)
        self.set_px(hx + (2 * dir_mult), y - 4, 8)  # Eye

        # Crushing Gigantic Mandibles
        jx = hx + (4 * dir_mult)
        self.rect(min(jx, jx + (2 * dir_mult)), y - 6, max(jx, jx + (2 * dir_mult)), y - 5, 16)
        self.rect(min(jx, jx + (2 * dir_mult)), y - 2, max(jx, jx + (2 * dir_mult)), y - 1, 16)
        self.set_px(jx + (3 * dir_mult), y - 4, 15)
        self.set_px(jx + (3 * dir_mult), y - 3, 15)

        # Quad-segment Heavy Armor Legs
        step = leg_frame % 2
        for lx in [-4, -1, 2, 5]:
            off = (1 if step else -1) if lx % 2 == 0 else (-1 if step else 1)
            self.set_px(x + (lx * dir_mult) + off, y, 6)
            self.set_px(x + (lx * dir_mult) + off, y - 1, 15)

    def draw_flyer_ant(self, x: int, y: int, facing_right: bool, wing_frame: int = 0):
        """Sleek 13x8 Alate / Flying Ant with translucent fluttering wings."""
        dir_mult = 1 if facing_right else -1

        # Slender Body
        ab_x = x - (4 * dir_mult)
        self.rect(min(x - dir_mult, ab_x), y - 3, max(x - dir_mult, ab_x), y - 1, 6)
        self.rect(min(x, x + (2 * dir_mult)), y - 2, max(x, x + (2 * dir_mult)), y - 1, 6)

        # Head & Antennae
        hx = x + (3 * dir_mult)
        self.rect(min(hx, hx + dir_mult), y - 3, max(hx, hx + dir_mult), y - 2, 6)
        self.set_px(hx + dir_mult, y - 4, 8)

        # Glistening Translucent Wings
        wing_flap = wing_frame % 3
        if wing_flap == 0:
            # Wings spread high
            self.rect(x - (4 * dir_mult), y - 7, x + (3 * dir_mult), y - 4, 14)
            self.set_px(x, y - 8, 13)
        elif wing_flap == 1:
            # Wings mid flap
            self.rect(x - (3 * dir_mult), y - 6, x + (4 * dir_mult), y - 4, 14)
            self.set_px(x + dir_mult, y - 6, 13)
        else:
            # Wings glide
            self.rect(x - (5 * dir_mult), y - 5, x + (2 * dir_mult), y - 4, 14)

        # Airborne Tucked Legs
        self.set_px(x - dir_mult, y, 6)
        self.set_px(x + dir_mult, y, 6)


def make_tier_gif(tier: int, filename: str) -> None:
    width = 240
    height = 88
    num_frames = 16
    delay = 8  # 80ms per frame (~12.5 FPS smooth animation)
    frames_data = []

    for f in range(num_frames):
        c = Canvas(width, height)
        c.draw_soil_background(f)

        # Tier-dependent ant population & behaviors
        if tier == 1:
            # Starter Colony: 3 dedicated workers
            # Worker 1: Upper tunnel transporting fungus food
            w1_x = (f * 12 + 15) % (width + 30) - 15
            c.draw_worker_ant(w1_x, 23, facing_right=True, carrying_type="food", leg_frame=f)

            # Worker 2: Upper tunnel returning with water
            w2_x = width - ((f * 11 + 60) % (width + 30))
            c.draw_worker_ant(w2_x, 23, facing_right=False, carrying_type="water", leg_frame=f)

            # Worker 3: Royal nurse tending eggs near the Queen
            nurse_x = 94 + (f % 4)
            c.draw_worker_ant(nurse_x, 53, facing_right=True, carrying_type="egg", leg_frame=f)

        elif tier == 2:
            # Growing Colony: 6 Workers + 1 Soldier Patrol
            # Upper highway workers
            for i, (offset, carrying) in enumerate([(10, "food"), (85, "water"), (160, "seed")]):
                wx = (f * 12 + offset) % (width + 30) - 15
                c.draw_worker_ant(wx, 23, facing_right=True, carrying_type=carrying, leg_frame=f + i)

            for i, (offset, carrying) in enumerate([(30, "none"), (120, "food")]):
                wx = width - ((f * 11 + offset) % (width + 30))
                c.draw_worker_ant(wx, 23, facing_right=False, carrying_type=carrying, leg_frame=f + i)

            # Left room: Gardener ant tending fungus
            g_x = 24 + (f % 3)
            c.draw_worker_ant(g_x, 53, facing_right=True, carrying_type="food", leg_frame=f)

            # Nurse ant in throne room
            c.draw_worker_ant(92 + (f % 3), 53, facing_right=True, carrying_type="egg", leg_frame=f)

            # Lower tunnel: Vigilant Soldier on patrol
            s_x = 40 + int(math.sin(f * math.pi / 8) * 35)
            c.draw_soldier_ant(s_x, 77, facing_right=(f < 8), leg_frame=f)

        elif tier == 3:
            # Thriving Colony: 10 Workers + 2 Soldiers + 1 Major Guard
            # Upper Highway 2-way traffic
            for i, (offset, carrying) in enumerate([(0, "food"), (60, "water"), (120, "seed"), (180, "food")]):
                wx = (f * 13 + offset) % (width + 30) - 15
                c.draw_worker_ant(wx, 23, facing_right=True, carrying_type=carrying, leg_frame=f + i)

            for i, (offset, carrying) in enumerate([(15, "water"), (80, "seed"), (150, "none")]):
                wx = width - ((f * 12 + offset) % (width + 30))
                c.draw_worker_ant(wx, 23, facing_right=False, carrying_type=carrying, leg_frame=f + i)

            # Fungus & Water attendants
            c.draw_worker_ant(18 + (f % 4), 53, facing_right=True, carrying_type="food", leg_frame=f)
            c.draw_worker_ant(195 + (f % 4), 53, facing_right=False, carrying_type="water", leg_frame=f)

            # 2 Royal attendants around the Queen
            c.draw_worker_ant(92, 53, facing_right=True, carrying_type="egg", leg_frame=f)
            c.draw_worker_ant(148, 53, facing_right=False, carrying_type="seed", leg_frame=f)

            # Lower Defense Patrol: 2 Soldiers
            s1_x = 35 + ((f * 10) % 80)
            c.draw_soldier_ant(s1_x, 77, facing_right=True, leg_frame=f)

            s2_x = width - 40 - ((f * 9) % 70)
            c.draw_soldier_ant(s2_x, 77, facing_right=False, leg_frame=f)

            # Fortress Major Ant guarding the nest gate
            major_x = 120 + (f % 2)
            c.draw_major_ant(major_x, 76, facing_right=True, leg_frame=f)

        else:
            # Tier 4: Grand Ant Empire: 15+ Workers + 3 Soldiers + 2 Major Guardians + 1 Flying Alate
            # Upper Highway Swarm
            for i, (offset, carrying) in enumerate([
                (0, "food"),
                (45, "water"),
                (90, "seed"),
                (135, "food"),
                (180, "water"),
                (220, "seed"),
            ]):
                wx = (f * 14 + offset) % (width + 30) - 15
                c.draw_worker_ant(wx, 23, facing_right=True, carrying_type=carrying, leg_frame=f + i)

            for i, (offset, carrying) in enumerate([
                (10, "seed"),
                (60, "food"),
                (110, "water"),
                (160, "food"),
                (210, "none"),
            ]):
                wx = width - ((f * 13 + offset) % (width + 30))
                c.draw_worker_ant(wx, 23, facing_right=False, carrying_type=carrying, leg_frame=f + i)

            # Flying Ant scouting the upper tunnel
            fl_x = (f * 16 + 30) % (width + 40) - 20
            c.draw_flyer_ant(fl_x, 16, facing_right=True, wing_frame=f)

            # Chamber workers
            c.draw_worker_ant(15 + (f % 4), 53, facing_right=True, carrying_type="food", leg_frame=f)
            c.draw_worker_ant(42 + (f % 4), 53, facing_right=False, carrying_type="food", leg_frame=f)
            c.draw_worker_ant(192 + (f % 4), 53, facing_right=False, carrying_type="water", leg_frame=f)
            c.draw_worker_ant(222 + (f % 4), 53, facing_right=True, carrying_type="water", leg_frame=f)

            # Royal court around the Queen
            c.draw_worker_ant(88, 53, facing_right=True, carrying_type="egg", leg_frame=f)
            c.draw_worker_ant(98, 53, facing_right=True, carrying_type="food", leg_frame=f)
            c.draw_worker_ant(142, 53, facing_right=False, carrying_type="seed", leg_frame=f)
            c.draw_worker_ant(152, 53, facing_right=False, carrying_type="water", leg_frame=f)

            # Soldiers marching formation in lower tunnels
            c.draw_soldier_ant(45 + (f * 6) % 60, 77, facing_right=True, leg_frame=f)
            c.draw_soldier_ant(190 - (f * 6) % 60, 77, facing_right=False, leg_frame=f)

            # 2 Colossal Major Guardians guarding the lower left & right fortress gates
            c.draw_major_ant(20, 76, facing_right=True, leg_frame=f)
            c.draw_major_ant(215, 76, facing_right=False, leg_frame=f)

        frames_data.append(c.grid)

    delays = [delay] * num_frames
    write_gif(filename, width, height, frames_data, delays, PALETTE)
    print(f"Generated high-res {filename} ({os.path.getsize(filename)} bytes)")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for t in range(1, 5):
        out_path = os.path.join(OUT_DIR, f"colony_working_t{t}.gif")
        make_tier_gif(t, out_path)


if __name__ == "__main__":
    main()
