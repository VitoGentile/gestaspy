import copy
import glob
import kinect
import mss
import numpy as np
import os
import pygame
import random
import statistics
import sys
from from_root import from_root
from PIL import Image, ImageOps
from pykinect2 import PyKinectV2
from threading import Timer

CRACK_PATHS = glob.glob(os.path.join(from_root("assets"), "cracks", "*.png"))
PUNCH_PATH = os.path.join(from_root("assets"), "punch.png")
CRACK_SOUNDS = glob.glob(os.path.join(from_root("assets"), "audio", "*.wav"))

N = 6


class BodyGameRuntime(object):
    def __init__(self, background_img, windowed_mode, show_pip):
        pygame.init()
        pygame.mouse.set_visible(False)

        # Init pygame mixer and load each song in each channel
        pygame.mixer.init()
        pygame.mixer.set_num_channels(len(CRACK_SOUNDS))

        # This will be used to limits the number of cracks to max 2 per second
        self._can_punch = True

        # True means the user wants a PiP is shown on the bottom right
        self._show_pip = show_pip

        # Set the width and height of the screen [width, height]
        self._infoObject = pygame.display.Info()

        if windowed_mode:
            self._screen = pygame.display.set_mode(
                (self._infoObject.current_w >> 1, self._infoObject.current_h >> 1),
                pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.RESIZABLE, 32)
        else:
            self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)

        pygame.display.set_caption("gestaspy")

        # Used to manage how fast the screen updates
        self._clock = pygame.time.Clock()

        # Kinect runtime object, we want IR if show_pip, and body frames always
        if show_pip:
            flags = (PyKinectV2.FrameSourceTypes_Infrared, PyKinectV2.FrameSourceTypes_Body)
        else:
            flags = (PyKinectV2.FrameSourceTypes_Body,)
        self._kinect = kinect.KinectManager(flags)

        # init frame surface with screenshot
        self._background_img = background_img
        self._frame_surface = None
        self.set_surface_from_img(self._background_img)

        # backup original background image (useful to reset)
        self._orig_background_img = copy.deepcopy(background_img)

        # here we will store skeleton data
        self._bodies = None

        # Create variables to store last hand positions
        self._hl = []
        self._hr = []

        # And also the ones computed for drawing the punches (will be used for smoothing filtering)
        self._punch_coord = {
            "l": [],
            "r": []
        }

        self._arm_lengths = {
            "l": [],
            "r": []
        }

    def reset_screen(self):
        self._background_img = copy.deepcopy(self._orig_background_img)

    def disable_draw_punch(self):
        # Disable to possibility to draw a new punch, and reenable it after 0.5 s
        self._can_punch = False

        t = Timer(0.5, self.enable_draw_punch)
        t.start()

    def enable_draw_punch(self):
        # reenable the possibility to draw new punch
        self._can_punch = True

    def set_surface_from_img(self, b_img):
        # Given a PIL image, this will set the next frame to be drawn by pygame
        self._frame_surface = pygame.image.fromstring(b_img.tobytes(), b_img.size, b_img.mode).convert()

    def draw_punch(self, joints):
        # Draw punch
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

        neck_spine_m = {
            "x": 0.5 * (joint_neck.Position.x + joint_spine.Position.x),
            "y": 0.5 * (joint_neck.Position.y + joint_spine.Position.y)
        }
        shoulders_length = (kinect.joint_distance(joint_shoulder_r, joint_neck) + kinect.joint_distance(joint_shoulder_l, joint_neck))
        neck_spine_length = kinect.joint_distance(joint_neck, joint_spine) * 1.5

        l_arm_length = kinect.joint_distance(joint_shoulder_l, joint_elbow_l) + kinect.joint_distance(joint_elbow_l, joint_wrist_l)
        r_arm_length = kinect.joint_distance(joint_shoulder_r, joint_elbow_r) + kinect.joint_distance(joint_elbow_r, joint_wrist_r)

        self._arm_lengths["l"].append(l_arm_length)
        if len(self._arm_lengths["l"]) > 50:
            self._arm_lengths["l"] = self._arm_lengths["l"][-50:]
        self._arm_lengths["r"].append(r_arm_length)
        if len(self._arm_lengths["r"]) > 50:
            self._arm_lengths["r"] = self._arm_lengths["r"][-50:]

        l_arm_length = statistics.mean(self._arm_lengths["l"])
        r_arm_length = statistics.mean(self._arm_lengths["r"])

        screen_w = self._frame_surface.get_width()
        screen_h = self._frame_surface.get_height()

        # Compute alpha value, will be used for both opacity and puch size
        alpha_dist_l = int(255 * (joint_spine.Position.z - joint_hand_left.Position.z - (0.2*l_arm_length)) / (l_arm_length * 0.8))
        alpha_dist_r = int(255 * (joint_spine.Position.z - joint_hand_right.Position.z - (0.2*r_arm_length)) / (r_arm_length * 0.8))

        alpha_dist_l = 0 if alpha_dist_l < 0 else alpha_dist_l
        alpha_dist_r = 0 if alpha_dist_r < 0 else alpha_dist_r
        alpha_dist_l = 255 if alpha_dist_l > 255 else alpha_dist_l
        alpha_dist_r = 255 if alpha_dist_r > 255 else alpha_dist_r

        l_punch_coord = None
        if joints[PyKinectV2.JointType_HandLeft].TrackingState != PyKinectV2.TrackingState_NotTracked:
            new_hl_x = ((joint_hand_left.Position.x - neck_spine_m["x"]) * screen_w / shoulders_length) + (screen_w/2)
            new_hl_y = -((joint_hand_left.Position.y - neck_spine_m["y"]) * screen_h / neck_spine_length) + (screen_h/2)
            l_punch_coord = new_hl_x, new_hl_y
            self.update_punch_coordinates(l_punch_coord, "l")
            self.add_punch("l", alpha=alpha_dist_l)
        else:
            self.update_punch_coordinates(None, "l")

        r_punch_coord = None
        if joints[PyKinectV2.JointType_HandRight].TrackingState != PyKinectV2.TrackingState_NotTracked:
            new_hr_x = ((joint_hand_right.Position.x - neck_spine_m["x"]) * screen_w / shoulders_length) + (screen_w/2)
            new_hr_y = -((joint_hand_right.Position.y - neck_spine_m["y"]) * screen_h / neck_spine_length) + (screen_h/2)
            r_punch_coord = new_hr_x, new_hr_y
            self.update_punch_coordinates(r_punch_coord, "r")
            self.add_punch("r", alpha=alpha_dist_r)
        else:
            self.update_punch_coordinates(None, "l")

        return l_punch_coord, r_punch_coord, alpha_dist_l == 255, alpha_dist_r == 255

    def add_crack(self, x, y, backup_img):
        # Add a new crack (if this possibility is enabled)
        if not self._can_punch:
            return

        crack = Image.open(random.choice(CRACK_PATHS)).convert("RGBA")
        screen_w = self._frame_surface.get_width()
        crack.thumbnail([int(screen_w * (0.1 + (random.random())/9)), sys.maxsize], Image.ANTIALIAS)

        self._background_img.paste(crack, (x, y), crack)
        backup_img.paste(crack, (x, y), crack)

        # Play sound
        s = random.randint(0, len(CRACK_SOUNDS)-1)
        pygame.mixer.Channel(s).play(pygame.mixer.Sound(CRACK_SOUNDS[s]))

        self.disable_draw_punch()

    def add_punch(self, side, alpha=255):
        # Draw the punch at specific location, with specific size and opacity based on alpha
        punch = Image.open(PUNCH_PATH)
        screen_w = self._frame_surface.get_width()
        pip_w = int(screen_w * 0.1 * ((0.2 + (alpha/170))**1.8))

        if pip_w <= 0:
            return

        punch.thumbnail([pip_w, sys.maxsize], Image.ANTIALIAS)

        a = int((alpha**3)/65025)
        pixels = punch.getdata()
        new_pixels = []
        for item in pixels:
            if item[3] < 200:
                new_pixels.append(item)
            else:
                new_pixels.append((item[0], item[1], item[2], a))
        punch.putdata(new_pixels)

        if side == "r":
            punch = ImageOps.mirror(punch)

        self._background_img.paste(punch, self.get_punch_filtered_coord(side), punch)

    def get_punch_filtered_coord(self, side):
        x = int(statistics.mean([x[0] for x in self._punch_coord[side] if side is not None]))
        y = int(statistics.mean([x[1] for x in self._punch_coord[side] if side is not None]))

        return x, y

    def get_z_filtered_coord(self, side):
        if side == "l":
            return statistics.mean([x.Position.z for x in self._hl if x is not None])
        else:
            return statistics.mean([x.Position.z for x in self._hr if x is not None])

    def add_pip(self):
        # add PiP
        f = self._kinect.get_ir_frame()
        if f is None:
            return

        ir_f8 = np.uint8(f.clip(1, 4000) / 16.)
        ir_frame8bit = np.dstack((ir_f8, ir_f8, ir_f8))
        ir_rgb = np.array(ir_frame8bit)
        ir_h, ir_w = self._kinect.get_ir_size()
        ir_rgb = ir_rgb.reshape((ir_h, ir_w, 3), order='C')

        im_pil = Image.fromarray(ir_rgb).convert("RGBA")

        # Resize image to 10% width
        screen_w = self._frame_surface.get_width()
        screen_h = self._frame_surface.get_height()
        pip_w = int(screen_w * 0.1)
        im_pil.thumbnail([pip_w, sys.maxsize], Image.ANTIALIAS)
        pip_w, pip_h = im_pil.size

        self._background_img.paste(im_pil, (screen_w-pip_w-15, screen_h-pip_h-15), im_pil)

    def update_hand_joints(self, joints):
        if joints is None:
            self._hl.append(None)
            self._hr.append(None)
        else:
            self._hl.append(joints[PyKinectV2.JointType_HandLeft])
            self._hr.append(joints[PyKinectV2.JointType_HandRight])

        if len(self._hl) > N:
            self._hl = self._hl[-N:]
        if len(self._hr) > N:
            self._hr = self._hr[-N:]

    def update_punch_coordinates(self, punch_coord, side):
        if punch_coord is None:
            self._punch_coord[side].append(None)
        else:
            self._punch_coord[side].append(punch_coord + (self.get_z_filtered_coord(side),))
            if len(self._punch_coord[side]) > N:
                self._punch_coord[side] = self._punch_coord[side][-N:]

    def get_h_joints_acceleration(self):
        z_l = [x[2] for x in self._punch_coord["l"] if not(x is None)]
        z_r = [x[2] for x in self._punch_coord["r"] if not(x is None)]

        if len(z_l) == N:
            # l_velocity = statistics.variance(z_l)
            l_velocity = z_l[-1] - z_l[0]
        else:
            l_velocity = None
        if len(z_r) == N:
            # r_velocity = statistics.variance(z_r)
            r_velocity = z_r[-1] - z_r[0]
        else:
            r_velocity = None

        return l_velocity, r_velocity

    def run(self):
        # Main Program Loop

        must_exit = False
        while True:
            # Main event loop
            for event in pygame.event.get():
                # User did something
                if event.type == pygame.QUIT:
                    # user clicked close
                    must_exit = True
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # user pressed key is ESC quit program
                    must_exit = True
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    # user pressed space key: reset screen
                    self.reset_screen()

            if must_exit:
                break

            self._bodies = self._kinect.get_body_frame()

            if self._show_pip:
                self.add_pip()

            # Save background image before adding additional stuff
            background_img_before_punch = copy.deepcopy(self._background_img)

            if self._bodies is not None:
                joints_processed = False
                for body in self._bodies.bodies:
                    if not body.is_tracked:
                        continue

                    joints = body.joints
                    self.update_hand_joints(joints)
                    joints_processed = True

                    l_punch_coord, r_punch_coord, punched_l, punched_r = self.draw_punch(joints)
                    l_acc, r_acc = self.get_h_joints_acceleration()

                    if punched_l and (l_acc is not None) and (l_acc > 0.005):
                        self.add_crack(*(self.get_punch_filtered_coord("l")), background_img_before_punch)
                    if punched_r and (r_acc is not None) and (r_acc > 0.005):
                        self.add_crack(*(self.get_punch_filtered_coord("r")), background_img_before_punch)

                    # No need to check for other bodies, use only one
                    break

                    # TODO automatic selection of nearest body

                if not joints_processed:
                    self.update_hand_joints(None)
            else:
                self.update_hand_joints(None)

            # Prepare surface
            self.set_surface_from_img(self._background_img)
            h_to_w = float(self._frame_surface.get_height()) / self._frame_surface.get_width()
            target_height = int(h_to_w * self._screen.get_width())
            surface_to_draw = pygame.transform.scale(self._frame_surface, (self._screen.get_width(), target_height))
            self._screen.blit(surface_to_draw, (0, 0))
            surface_to_draw = None

            pygame.display.update()

            # update the screen with what we've drawn
            pygame.display.flip()

            # limit to 60 frames per second
            self._clock.tick(60)

            # Restore original background_image to what it was before drawing punches
            self._background_img = background_img_before_punch

        # quit
        self._kinect.stop()
        pygame.quit()


def start_game(windowed_mode=False, show_pip=False):
    with mss.mss() as sct:
        sct_img = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    game = BodyGameRuntime(img, windowed_mode, show_pip)
    game.run()