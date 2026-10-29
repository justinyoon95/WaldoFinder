"""Convex four-corner exclusions in original pixel coordinates."""

import math


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])


def valid_polygon(points, width, height):
    """Require four distinct, in-bounds corners in clockwise or reverse order.

    Strict convexity rejects crossed edges, concave shapes and collinear corners.
    """
    if not isinstance(points, list) or len(points) != 4:
        return False
    for point in points:
        if (not isinstance(point, list) or len(point) != 2
                or any(type(n) not in (int, float) or not math.isfinite(n) for n in point)
                or not 0 <= point[0] <= width or not 0 <= point[1] <= height):
            return False
    turns = [cross(points[i], points[(i+1) % 4], points[(i+2) % 4]) for i in range(4)]
    return all(t > 0 for t in turns) or all(t < 0 for t in turns)


def box_points(box):
    x1, y1, x2, y2 = box
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def region_points(region):
    return region["points"] if "points" in region else box_points(region["bbox"])


def all_exclusions(scene):
    return scene["exclusion_rectangles"] + scene.get("exclusion_polygons", [])


def region_overlaps_box(region, box):
    """Separating-axis test: positive-area overlap, not bounding-box overlap.

    Inputs must already be validated as a convex polygon and a positive box.
    A shared edge or point alone is not an overlap.
    """
    polygon = region_points(region)
    corners = box_points(box)
    axes = [(1, 0), (0, 1)]
    for i, point in enumerate(polygon):
        following = polygon[(i+1) % len(polygon)]
        axes.append((-(following[1]-point[1]), following[0]-point[0]))
    for ax, ay in axes:
        panel_projection = [x*ax + y*ay for x, y in polygon]
        box_projection = [x*ax + y*ay for x, y in corners]
        if max(panel_projection) <= min(box_projection) or max(box_projection) <= min(panel_projection):
            return False
    return True


def region_contains_box(region, box):
    polygon = region_points(region)
    for point in box_points(box):
        sides = [cross(polygon[i], polygon[(i+1) % len(polygon)], point) for i in range(len(polygon))]
        if not (all(s >= 0 for s in sides) or all(s <= 0 for s in sides)):
            return False
    return True
