import math
from pykinect2 import PyKinectV2
from pykinect2 import PyKinectRuntime


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


class KinectManager:
    def __init__(self, flags: tuple):
        if len(flags) == 0:
            raise ValueError("At least one flag is expected")

        flag = flags[0]
        for f in flags[1:]:
            flag = flag | f

        self._kinect = PyKinectRuntime.PyKinectRuntime(flag)

        self._ir_frame = None
        self._body_frame = None

    def stop(self):
        self._kinect.close()

    def get_ir_frame(self):
        if self._kinect.has_new_infrared_frame():
            self._ir_frame = self._kinect.get_last_infrared_frame()

        return self._ir_frame

    def get_ir_size(self) -> tuple:
        """
        :return: H, W
        """

        return self._kinect.infrared_frame_desc.Height, self._kinect.infrared_frame_desc.Width

    def get_body_frame(self):
        if self._kinect.has_new_body_frame():
            self._body_frame = self._kinect.get_last_body_frame()

        return self._body_frame

    def get_max_body_count(self):
        return self._kinect.max_body_count
