import pygame

from skins.shapes import bean


class GamecubeSkin:
    def __init__(self):
        self.design_width = 420
        self.design_height = 300

        # Button indices (typical XInput order: A=0, B=1, X=2, Y=3, LB=4, RB=5, Back=6, Start=7, LS=8, RS=9)
        # GameCube mapping
        self.btn_map = {
            "A": 0,
            "B": 2,
            "X": 1,
            "Y": 3,
            "START": 7,
            "Z": 5,
        }

        self.axis_map = {
            "LX": 0, "LY": 1,
            "RX": 2, "RY": 3,
            "LT": 4, "RT": 5,
        }

        self.pos = {
            "LTRIG": (80, 0, 60, 75),
            "RTRIG": (280, 0, 60, 75),

            "LS": (95, 135),
            "DPAD": (165, 235),

            "A": (315, 140),
            "B": (280, 165),

            "Y": (315, 115),
            "X": (340, 130),

            "START": (210, 150),

            "CS": (275, 235),
            "Z": (310, 95),
        }

        self.stick_travel = 10

    def _S(self, x, y, s):
        return int(x * s), int(y * s)

    def _R(self, x, y, w, h, s):
        return pygame.Rect(int(x * s), int(y * s), int(w * s), int(h * s))

    def _glow_circle(self, surf, center, r, color, on):
        if on:
            pygame.draw.circle(surf, (255, 255, 255), center, r + 4)
        pygame.draw.circle(surf, color, center, r)
        pygame.draw.circle(surf, (0, 0, 0), center, r, 2)

    def _trigger_vertical(self, surf, rect, amt, scale):
        pygame.draw.rect(
            surf,
            (255, 255, 255),
            rect,
            width=max(1, int(2 * scale)),
            border_radius=int(12 * scale),
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

        pygame.draw.rect(
            surf,
            hi if hy == 1 else lo,
            pygame.Rect(cx - v // 2, cy - t // 2, v, t // 2),
            border_radius=int(5 * scale),
        )
        pygame.draw.rect(
            surf,
            hi if hy == -1 else lo,
            pygame.Rect(cx - v // 2, cy, v, t // 2),
            border_radius=int(5 * scale),
        )
        pygame.draw.rect(
            surf,
            hi if hx == -1 else lo,
            pygame.Rect(cx - w // 2, cy - h // 2, w // 2, h),
            border_radius=int(5 * scale),
        )
        pygame.draw.rect(
            surf,
            hi if hx == 1 else lo,
            pygame.Rect(cx, cy - h // 2, w // 2, h),
            border_radius=int(5 * scale),
        )

    def draw(self, screen, inp, dz, norm_trigger, scale):
        # Triggers
        ltx, lty, ltw, lth = self.pos["LTRIG"]
        rtx, rty, rtw, rth = self.pos["RTRIG"]

        self._trigger_vertical(screen, self._R(ltx, lty, ltw, lth, scale), norm_trigger(inp.axis("LT")), scale)
        self._trigger_vertical(screen, self._R(rtx, rty, rtw, rth, scale), norm_trigger(inp.axis("RT")), scale)

        # Sticks
        lx = dz(inp.axis("LX"))
        ly = dz(inp.axis("LY"))
        rx = dz(inp.axis("RX"))
        ry = dz(inp.axis("RY"))

        ls_center = self._S(*self.pos["LS"], scale)
        cs_center = self._S(*self.pos["CS"], scale)

        travel = int(self.stick_travel * scale)

        self._stick(screen, ls_center, lx, ly, travel, scale, (80, 80, 80), (255, 255, 255))
        self._stick(screen, cs_center, rx, ry, int(travel * 0.85), scale, (230, 200, 40), (255, 240, 120))

        # Dpad
        hx, hy = inp.hat(0)
        dpad_center = self._S(*self.pos["DPAD"], scale)
        self._dpad_plus(screen, dpad_center, hx, hy, scale)

        # A / B
        a_center = self._S(*self.pos["A"], scale)
        b_center = self._S(*self.pos["B"], scale)

        self._glow_circle(screen, a_center, int(20 * scale), (70, 220, 200), inp.button("A"))
        self._glow_circle(screen, b_center, int(12 * scale), (230, 60, 60), inp.button("B"))

        # Y / X beans (grey), pressed -> white "background bean" slightly larger
        y_center = self._S(*self.pos["Y"], scale)
        x_center = self._S(*self.pos["X"], scale)

        # Shared geometry
        y_rx = 10 * scale # Curve length
        y_ry = 7.5 * scale # Curve height
        y_th = 10 * scale # Thickness
        y_rot = 0

        x_rx = 10 * scale # Curve length
        x_ry = 7.5 * scale # Curve height
        x_th = 10 * scale # Thickness
        x_rot = 45

        grey = (170, 170, 170)

        # --- Y ---
        if inp.button("Y"):
            bean.draw(
                screen,
                center=y_center,
                rx=y_rx * 1.10,
                ry=y_ry * 1.10,
                thickness=y_th * 1.25,
                start_deg=20,
                end_deg=160,
                rotation_deg=y_rot,
                color=(255, 255, 255),
                steps=40,
            )

        bean.draw(
            screen,
            center=y_center,
            rx=y_rx,
            ry=y_ry,
            thickness=y_th,
            start_deg=20,
            end_deg=160,
            rotation_deg=y_rot,
            color=grey,
            steps=40,
        )

        # --- X ---
        if inp.button("X"):
            bean.draw(
                screen,
                center=x_center,
                rx=x_rx * 1.10,
                ry=x_ry * 1.10,
                thickness=x_th * 1.25,
                start_deg=20,
                end_deg=160,
                rotation_deg=x_rot,
                color=(255, 255, 255),
                steps=40,
            )

        bean.draw(
            screen,
            center=x_center,
            rx=x_rx,
            ry=x_ry,
            thickness=x_th,
            start_deg=20,
            end_deg=160,
            rotation_deg=x_rot,
            color=grey,
            steps=40,
        )

        # Start
        start_center = self._S(*self.pos["START"], scale)
        self._glow_circle(screen, start_center, int(8 * scale), (220, 220, 220), inp.button("START"))

        # Z
        zx, zy = self.pos["Z"]
        zc = self._S(zx, zy, scale)

        z_rect = pygame.Rect(
            zc[0] - int(26 * scale),
            zc[1] - int(10 * scale),
            int(50 * scale),
            int(10 * scale),
        )

        pygame.draw.rect(
            screen,
            (255, 255, 255) if inp.button("Z") else (100, 100, 200),
            z_rect,
            border_radius=int(999 * scale),
        )


def build():
    return GamecubeSkin()