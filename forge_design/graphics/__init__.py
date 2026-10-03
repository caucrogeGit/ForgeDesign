"""Géométrie graphique côté serveur, sans domaine ni HTTP.

À ne pas confondre avec ``forge_design/web/static/graphics/`` (moteur
JavaScript navigateur) : ce paquet calcule des géométries pour les layouts
serveur qui produisent les GraphicScene.
"""

from forge_design.graphics.lanes import (
    HorizontalSpan,
    LanePlan,
    allocate_horizontal_lanes,
    lane_label_position,
    route_via_horizontal_lane,
    svg_path,
)

__all__ = [
    "HorizontalSpan",
    "LanePlan",
    "allocate_horizontal_lanes",
    "lane_label_position",
    "route_via_horizontal_lane",
    "svg_path",
]
