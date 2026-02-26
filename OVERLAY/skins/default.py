import pygame


class DefaultSkin:
    def __init__(self):
        # Design-space canvas
        self.design_width = 420
        self.design_height = 260

        # Button indices (typical XInput order: A=0, B=1, X=2, Y=3, LB=4, RB=5, Back=6, Start=7, LS=8, RS=9)
        # If your controller differs, you can adjust these numbers.
        self.btn_map = {
            "A": 0,
            "B": 1,
            "X": 2,
            "Y": 3,
            "LB": 4,
            "RB": 5,
            "BACK": 6,
            "START": 7,
            "LS": 8,
            "RS": 9,
        }

        # Axis indices (common XInput)
        # LX/LY = left stick, RX/RY = right stick, LT/RT = triggers
        self.axis_map = {
            "LX": 0, "LY": 1,
            "RX": 2, "RY": 3,
            "LT": 4, "RT": 5,
        }

        # Layout (design-space)
        self.pos = {
            # triggers (x, y, w, h)
            "LTRIG": (40, 10, 60, 78),
            "RTRIG": (320, 10, 60, 78),

            # bumpers (x, y, w, h)
            "LB": (38, 95, 90, 22),
            "RB": (292, 95, 90, 22),

            # sticks (centers)
            "LS": (110, 150),
            "RS": (265, 180),

            # dpad center
            "DPAD": (170, 190),

            # face buttons centers
            "A": (340, 195),
            "B": (370, 165),
            "X": (310, 165),
            "Y": (340, 135),

            # start/back centers
            "BACK": (195, 125),
            "START": (225, 125),
        }

        self.stick_travel = 10

    # ---------- helpers ----------
    def _S(self, x, y, s):
        return int(x * s), int(y * s)

    def _R(self, x, y, w, h, s):
        return pygame.Rect(int(x * s), int(y * s), int(w * s), int(h * s))

    def _glow_circle(self, surf, center, r, fill, on, scale):
        if on:
            pygame.draw.circle(surf, (255, 255, 255), center, r + int(4 * scale))
        pygame.draw.circle(surf, fill, center, r)
        pygame.draw.circle(surf, (0, 0, 0), center, r, max(1, int(2 * scale)))

    def _pill(self, surf, rect, fill, on, scale):
        if on:
            glow = rect.inflate(int(10 * scale), int(8 * scale))
            pygame.draw.rect(surf, (255, 255, 255), glow, border_radius=int(999 * scale))
        pygame.draw.rect(surf, fill, rect, border_radius=int(999 * scale))
        pygame.draw.rect(surf, (0, 0, 0), rect, width=max(1, int(2 * scale)), border_radius=int(999 * scale))

    def _trigger_vertical(self, surf, rect, amt, scale):
        pygame.draw.rect(
            surf, (255, 255, 255), rect,
            width=max(1, int(2 * scale)),
            border_radius=int(12 * scale)
        )
        pad = max(1, int(3 * scale))
        inner = pygame.Rect(rect.x + pad, rect.y + pad, rect.w - 2 * pad, rect.h - 2 * pad)
        pygame.draw.rect(surf, (70, 70, 70), inner, border_radius=int(10 * scale))

        fill_h = int(inner.h * amt)
        fill = pygame.Rect(inner.x, inner.y + inner.h - fill_h, inner.w, fill_h)
        pygame.draw.rect(surf, (255, 255, 255), fill, border_radius=int(10 * scale))

    def _stick(self, surf, center, x, y, travel, scale, base_col, nub_col):
        pygame.draw.circle(surf, (40, 40, 40), center, int(26 * scale))
        pygame.draw.circle(surf, base_col, center, int(22 * scale))
        nx = int(center[0] + x * travel)
        ny = int(center[1] + y * travel)
        pygame.draw.circle(surf, nub_col, (nx, ny), int(8 * scale))

    def _dpad_plus(self, surf, center, hx, hy, scale):
        cx, cy = center
        w = int(58 * scale)
        h = int(16 * scale)
        t = int(58 * scale)
        v = int(16 * scale)

        horiz = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        vert = pygame.Rect(cx - v // 2, cy - t // 2, v, t)

        base = (210, 210, 210)
        edge = (30, 30, 30)

        pygame.draw.rect(surf, base, horiz, border_radius=int(6 * scale))
        pygame.draw.rect(surf, base, vert, border_radius=int(6 * scale))
        pygame.draw.rect(surf, edge, horiz, width=max(1, int(2 * scale)), border_radius=int(6 * scale))
        pygame.draw.rect(surf, edge, vert, width=max(1, int(2 * scale)), border_radius=int(6 * scale))

        hi = (255, 255, 255)
        lo = (155, 155, 155)

        pygame.draw.rect(surf, hi if hy == 1 else lo, pygame.Rect(cx - v // 2, cy - t // 2, v, t // 2), border_radius=int(5 * scale))
        pygame.draw.rect(surf, hi if hy == -1 else lo, pygame.Rect(cx - v // 2, cy, v, t // 2), border_radius=int(5 * scale))
        pygame.draw.rect(surf, hi if hx == -1 else lo, pygame.Rect(cx - w // 2, cy - h // 2, w // 2, h), border_radius=int(5 * scale))
        pygame.draw.rect(surf, hi if hx == 1 else lo, pygame.Rect(cx, cy - h // 2, w // 2, h), border_radius=int(5 * scale))

    # ---------- draw ----------
    def draw(self, screen, inp, dz, norm_trigger, scale):
        # Triggers
        ltx, lty, ltw, lth = self.pos["LTRIG"]
        rtx, rty, rtw, rth = self.pos["RTRIG"]
        self._trigger_vertical(screen, self._R(ltx, lty, ltw, lth, scale), norm_trigger(inp.axis("LT")), scale)
        self._trigger_vertical(screen, self._R(rtx, rty, rtw, rth, scale), norm_trigger(inp.axis("RT")), scale)

        # Bumpers
        lb_rect = self._R(*self.pos["LB"], scale)
        rb_rect = self._R(*self.pos["RB"], scale)
        self._pill(screen, lb_rect, (140, 140, 140), inp.button("LB"), scale)
        self._pill(screen, rb_rect, (140, 140, 140), inp.button("RB"), scale)

        # Sticks
        lx = dz(inp.axis("LX"))
        ly = dz(inp.axis("LY"))
        rx = dz(inp.axis("RX"))
        ry = dz(inp.axis("RY"))

        ls = self._S(*self.pos["LS"], scale)
        rs = self._S(*self.pos["RS"], scale)
        travel = int(self.stick_travel * scale)

        self._stick(screen, ls, lx, ly, travel, scale, base_col=(80, 80, 80), nub_col=(255, 255, 255))
        self._stick(screen, rs, rx, ry, travel, scale, base_col=(80, 80, 80), nub_col=(255, 255, 255))

        # D-pad
        hx, hy = inp.hat(0)
        dp = self._S(*self.pos["DPAD"], scale)
        self._dpad_plus(screen, dp, hx, hy, scale)

        # ABXY
        self._glow_circle(screen, self._S(*self.pos["A"], scale), int(14 * scale), (70, 220, 200), inp.button("A"), scale)
        self._glow_circle(screen, self._S(*self.pos["B"], scale), int(14 * scale), (230, 60, 60), inp.button("B"), scale)
        self._glow_circle(screen, self._S(*self.pos["X"], scale), int(14 * scale), (90, 140, 255), inp.button("X"), scale)
        self._glow_circle(screen, self._S(*self.pos["Y"], scale), int(14 * scale), (240, 230, 80), inp.button("Y"), scale)

        # Back/Start
        self._glow_circle(screen, self._S(*self.pos["BACK"], scale), int(8 * scale), (220, 220, 220), inp.button("BACK"), scale)
        self._glow_circle(screen, self._S(*self.pos["START"], scale), int(8 * scale), (220, 220, 220), inp.button("START"), scale)


def build():
    return DefaultSkin()