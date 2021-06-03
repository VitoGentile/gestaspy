import math


def joint_distance(j1, j2) -> float:
    """
    Compute Euclidean distance between two Kinect joints
    :param j1: joint 1
    :param j2: joint 1
    :return: distance
    """

    x = (j1.Position.x - j2.Position.x)**2
    y = (j1.Position.y - j2.Position.y)**2
    z = (j1.Position.z - j2.Position.z)**2
    return math.sqrt(x + y + z)
