"""
Bean shape primitive for controller skins.

Usage:
    from shapes.bean import draw

    draw(
        surface,
        center=(x, y),
        rx=40,
        ry=25,
        thickness=12,
        start_deg=20,
        end_deg=160,
        rotation_deg=45,
        color=(255,255,255)
    )
"""

import pygame
import math


def _rotate(pt, center, deg):
    """Rotate a point around center."""
    if deg == 0:
        return pt

    rad = math.radians(deg)
    ox, oy = center
    px, py = pt

    qx = ox + math.cos(rad) * (px - ox) - math.sin(rad) * (py - oy)
    qy = oy + math.sin(rad) * (px - ox) + math.cos(rad) * (py - oy)
    return (qx, qy)


def draw(
    surface,
    center,
    rx,
    ry,
    thickness,
    start_deg=20,
    end_deg=160,
    rotation_deg=0,
    color=(255, 255, 255),
    steps=40,
):
    """
    Draw a curved bean/tube shape.

    Parameters
    ----------
    surface : pygame.Surface
        Target surface
    center : (x,y)
        Center of ellipse arc
    rx : float
        Horizontal ellipse radius
    ry : float
        Vertical ellipse radius
    thickness : float
        Tube thickness
    start_deg : float
        Arc start angle
    end_deg : float
        Arc end angle
    rotation_deg : float
        Rotation of whole bean
    color : tuple
        RGB color
    steps : int
        Curve smoothness
    """

    cx, cy = center

    center_pts = []

    start = math.radians(start_deg)
    end = math.radians(end_deg)

    for i in range(steps + 1):
        t = start + (end - start) * i / steps
        x = cx + math.cos(t) * rx
        y = cy - math.sin(t) * ry
        center_pts.append((x, y))

    left = []
    right = []

    for i in range(len(center_pts)):
        if i == 0:
            dx = center_pts[1][0] - center_pts[0][0]
            dy = center_pts[1][1] - center_pts[0][1]
        else:
            dx = center_pts[i][0] - center_pts[i - 1][0]
            dy = center_pts[i][1] - center_pts[i - 1][1]

        length = math.hypot(dx, dy)
        if length == 0:
            continue

        nx = -dy / length
        ny = dx / length

        left.append(
            (center_pts[i][0] + nx * thickness / 2, center_pts[i][1] + ny * thickness / 2)
        )
        right.append(
            (center_pts[i][0] - nx * thickness / 2, center_pts[i][1] - ny * thickness / 2)
        )

    poly = left + right[::-1]

    if rotation_deg != 0:
        poly = [_rotate(p, center, rotation_deg) for p in poly]
        start_pt = _rotate(center_pts[0], center, rotation_deg)
        end_pt = _rotate(center_pts[-1], center, rotation_deg)
    else:
        start_pt = center_pts[0]
        end_pt = center_pts[-1]

    pygame.draw.polygon(surface, color, poly)

    pygame.draw.circle(surface, color, start_pt, int(thickness / 2))
    pygame.draw.circle(surface, color, end_pt, int(thickness / 2))