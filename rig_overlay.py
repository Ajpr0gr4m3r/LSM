"""Puntos visibles del mismo fotograma usado por reconocimiento y captura."""
from math import isfinite

import numpy as np
from recognition_features import regions


# Construye el formato auxiliar heredado del rig; el protocolo web activo usa hand_rig.
def rig_payload(points, width, height):
    pose, face, left, right = regions(np.asarray(points))

    # Convierte puntos finitos y visibles en coordenadas para el formato auxiliar.
    def visible_points(region, visibility=False):
        output = []
        for point in region:
            present = np.any(point[:3] != 0) and np.isfinite(point).all()
            if visibility:
                present = present and point[3] >= .5
            output.append([float(point[0]), float(point[1])] if present else None)
        return output

    return {'width': width, 'height': height, 'pose': visible_points(pose, True),
            'face': visible_points(face), 'left': visible_points(left), 'right': visible_points(right)}


# Índices de MediaPipe Pose para nariz, ojos, orejas, hombros y caderas.
UPPER_BODY_INDICES = (0, 2, 5, 7, 8, 11, 12, 23, 24)


def upper_body_rig(pose):
    """Proyecta los puntos visibles de la cabeza y el torso en el fotograma."""
    if pose is None:
        return {}
    points = {}
    for index in UPPER_BODY_INDICES:
        point = pose.landmark[index]
        if (point.visibility >= .5 and isfinite(point.x) and isfinite(point.y)
                and 0 <= point.x <= 1 and 0 <= point.y <= 1):
            points[index] = [round(point.x, 5), round(point.y, 5)]
    return points
