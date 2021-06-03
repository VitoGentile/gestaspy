import datetime
from abc import ABC, abstractmethod
from PIL import Image


class DeviceNotStartedException(Exception):
    pass


class ColorFrame:
    def __init__(self, img: Image):
        self._timestamp = datetime.datetime.now()
        self._img = img

    def get_timestamp(self):
        return self._timestamp

    def get_img(self) -> Image:
        return self._img


class HandJointsFrame:
    def __init__(self, hl: (float, float, float), hr: (float, float, float)):
        self._timestamp = datetime.datetime.now()
        self._hand_joints = {
            "l": None,
            "r": None
        }

        if not(hl is None):
            self._hand_joints["l"] = {
                "x": hl[0],
                "y": hl[1],
                "z": hl[2]
            }
        if not(hr is None):
            self._hand_joints["r"] = {
                "x": hr[0],
                "y": hr[1],
                "z": hr[2]
            }

    def get_timestamp(self):
        return self._timestamp

    def get_hand_joints(self):
        return self._hand_joints


class DeviceManager(ABC):
    @abstractmethod
    def get_last_hand_joints_frame(self) -> HandJointsFrame:
        """
        should return the hands' coordinates, where:
            - all the coordinates are centered in the mid point between neck and spine base
            - x is normalized so the it's 0 if on the neck-spine axis, and it's +/-1 if on the same x of shoulder
            - y is normalized so the it's 0 if on the perpendicular of the neck-spine axis, and it's +/-1 if on
              the same y of neck/spine base
            - z is the depth, normalized so that it's 0 on the spine-neck axis, and 1 if equal or greater of the
              user's arm length
        """
        pass

    @abstractmethod
    def get_last_color_frame(self) -> ColorFrame:
        pass

    @abstractmethod
    def set_filter_parameters(self, parameters):
        pass

    @abstractmethod
    def stop_device(self):
        pass

    @abstractmethod
    def start_device(self):
        pass

    @abstractmethod
    def is_device_started(self) -> bool:
        pass

    @abstractmethod
    def get_hand_joints_velocities(self) -> (float, float):
        pass
