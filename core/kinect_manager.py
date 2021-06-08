import numpy as np
import statistics
from PIL import Image
from pykinect2 import PyKinectRuntime, PyKinectV2
from typing import Optional

from core.device_manager import DeviceManager, DeviceNotStartedException, ColorFrame, HandJointsFrame
from core.utils import joint_distance


class KinectManager(DeviceManager):
    def __init__(self):
        self._kinect = None

        self._color_frame = None
        self._hand_frames = []

        self.__arm_lengths = {
            "l": [],
            "r": []
        }

        # Max num of last hand frames stored
        self._n = 10

    def get_last_hand_joints_frame(self) -> Optional[HandJointsFrame]:
        if not self.is_device_started():
            raise DeviceNotStartedException("Device not started")

        joints_processed = False
        if self._kinect.has_new_body_frame():
            bodies = self._kinect.get_last_body_frame()
            if bodies is not None:
                for body in bodies.bodies:
                    if not body.is_tracked:
                        continue

                    joints_processed = True

                    joints = body.joints
                    if not(joints is None):
                        hl, hr = self.__normalize_hand_joints(joints)
                        self._hand_frames.append(HandJointsFrame(hl, hr))

                    self.__clean_old_hand_frames()

                    # No need to check for other bodies, use only one
                    break
                    # TODO automatic selection of nearest body

        if not joints_processed:
            self._hand_frames.append(HandJointsFrame(None, None))

        if len(self._hand_frames) > 0:
            return self.__get_last_filtered_frame()
        else:
            return None

    def get_hand_joints_velocities(self) -> (float, float):
        if len(self._hand_frames) == 0:
            return None, None

        velocity = dict()
        for side in {"l", "r"}:
            z_l = [x.get_hand_joints()[side]["z"] for x in self._hand_frames if not (x is None) and (x.get_hand_joints()[side] is not None)]

            if len(z_l) == self._n:
                # velocity[side] = statistics.variance(z_l)
                velocity[side] = z_l[-self._n+3] - z_l[0]
            else:
                velocity[side] = None

        return velocity["l"], velocity["r"]

    def __normalize_hand_joints(self, joints) -> ((float, float, float), (float, float, float)):
        joint_hand_left = joints[PyKinectV2.JointType_HandLeft]
        joint_hand_right = joints[PyKinectV2.JointType_HandRight]

        joint_neck = joints[PyKinectV2.JointType_Neck]
        joint_spine = joints[PyKinectV2.JointType_SpineBase]
        joint_shoulder_r = joints[PyKinectV2.JointType_ShoulderRight]
        joint_shoulder_l = joints[PyKinectV2.JointType_ShoulderLeft]
        joint_elbow_r = joints[PyKinectV2.JointType_ElbowRight]
        joint_elbow_l = joints[PyKinectV2.JointType_ElbowLeft]
        joint_wrist_r = joints[PyKinectV2.JointType_WristRight]
        joint_wrist_l = joints[PyKinectV2.JointType_WristLeft]

        # If any of the above is not tracked, return None, None
        can_normalize = True
        joints_states = {
            joint_neck.TrackingState,
            joint_spine.TrackingState,
            joint_shoulder_r.TrackingState,
            joint_shoulder_l.TrackingState,
            joint_elbow_r.TrackingState,
            joint_elbow_l.TrackingState,
            joint_wrist_r.TrackingState,
            joint_wrist_l.TrackingState
        }
        for js in joints_states:
            if js == PyKinectV2.TrackingState_NotTracked:
                can_normalize = False

        if not can_normalize:
            return None, None

        # TrackingState of hand joints is checked separately
        res = [None, None]
        for i, hj in enumerate((joint_hand_left, joint_hand_right)):
            if hj.TrackingState == PyKinectV2.TrackingState_NotTracked:
                continue

            neck_spine_m = {
                "x": 0.5 * (joint_neck.Position.x + joint_spine.Position.x),
                "y": 0.5 * (joint_neck.Position.y + joint_spine.Position.y),
                "z": 0.5 * (joint_neck.Position.z + joint_spine.Position.z)
            }
            shoulders_length = joint_distance(joint_shoulder_r, joint_neck) + joint_distance(joint_shoulder_l, joint_neck)
            neck_spine_length = joint_distance(joint_neck, joint_spine)

            l_arm_length = joint_distance(joint_shoulder_l, joint_elbow_l) + joint_distance(joint_elbow_l, joint_wrist_l)
            r_arm_length = joint_distance(joint_shoulder_r, joint_elbow_r) + joint_distance(joint_elbow_r, joint_wrist_r)

            self.__arm_lengths["l"].append(l_arm_length)
            if len(self.__arm_lengths["l"]) > 50:
                self.__arm_lengths["l"] = self.__arm_lengths["l"][-50:]
            self.__arm_lengths["r"].append(r_arm_length)
            if len(self.__arm_lengths["r"]) > 50:
                self.__arm_lengths["r"] = self.__arm_lengths["r"][-50:]

            l_arm_length = statistics.mean(self.__arm_lengths["l"])
            r_arm_length = statistics.mean(self.__arm_lengths["r"])

            # all the coordinates are centered in the mid point between neck and spine base
            res[i] = [hj.Position.x, hj.Position.y, hj.Position.z]

            # x is normalized so that it's 0 if on the neck-spine axis, and it's +/-1 if on the same x of shoulders
            res[i][0] -= neck_spine_m["x"]
            res[i][0] /= shoulders_length

            # y is normalized so the it's 0 if on the perpendicular of the neck-spine axis, and it's +/-1 if on
            # the same y of neck/spine base
            res[i][1] -= neck_spine_m["y"]
            res[i][1] /= neck_spine_length

            # z is the depth, normalized so that it's 0 on the spine-neck plane, and 1 if equal to user's arm length
            res[i][2] -= neck_spine_m["z"]
            if i == 0:
                # left
                res[i][2] = res[i][2] / l_arm_length
            else:
                # right
                res[i][2] = res[i][2] / r_arm_length
            res[i][2] = -res[i][2]

        return res

    def __clean_old_hand_frames(self):
        if len(self._hand_frames) > self._n:
            self._hand_frames = self._hand_frames[-self._n:]

    def __compute_weighted_avg(self, hand_frames):
        weights = list(range(1, len(self._hand_frames) + 1))
        weights_l = [w for i, w in enumerate(weights) if hand_frames[i] is not None]

        if len(weights_l) == 0:
            l_out = None
        else:
            l_out = [0, 0, 0]
            i = 0
            for hl in hand_frames:
                if hl is None:
                    continue

                w = weights[i] / sum(weights_l)

                l_out[0] += hl["x"] * w
                l_out[1] += hl["y"] * w
                l_out[2] += hl["z"] * w
                i += 1

        return l_out

    def __get_last_filtered_frame(self):
        l_out = self.__compute_weighted_avg([hf.get_hand_joints()["l"] for hf in self._hand_frames])
        r_out = self.__compute_weighted_avg([hf.get_hand_joints()["r"] for hf in self._hand_frames])

        return HandJointsFrame(l_out, r_out)

    def get_last_color_frame(self) -> Optional[ColorFrame]:
        if not self.is_device_started():
            raise DeviceNotStartedException("Device not started")

        if self._kinect.has_new_color_frame():
            f = self._kinect.get_last_color_frame()
        else:
            return None

        ir_rgb = np.array(f)
        ir_w, ir_h = self._kinect.color_frame_desc.Width, self._kinect.color_frame_desc.Height
        ir_rgb = ir_rgb.reshape((ir_h, ir_w, 4))
        ir_rgb[:, :, [0, 2]] = ir_rgb[:, :, [2, 0]]

        self._color_frame = ColorFrame(Image.fromarray(ir_rgb).convert("RGBA"))

        return self._color_frame

    def set_filter_parameters(self, n: float):
        self._n = n

    def stop_device(self):
        if self.is_device_started():
            self._kinect.close()

    def start_device(self):
        if not(self.is_device_started()):
            self._kinect = PyKinectRuntime.PyKinectRuntime(
                PyKinectV2.FrameSourceTypes_Color | PyKinectV2.FrameSourceTypes_Body)

    def is_device_started(self) -> bool:
        return not(self._kinect is None)
