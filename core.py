import copy
import glob
import math
import mss
import numpy as np
import os
import pygame
import random
import sys
from PIL import Image, ImageOps
from pykinect2 import PyKinectV2
from pykinect2 import PyKinectRuntime
from threading import Timer

CRACK_PATHS = glob.glob(os.path.join("assets", "cracks", "*.png"))
PUNCH_PATH = os.path.join("assets", "punch.png")
CRACK_SOUNDS = glob.glob(os.path.join("assets", "audio", "*.wav"))


def dist(j1, j2):
    return math.sqrt(((j1.Position.x - j2.Position.x)**2) + ((j1.Position.y - j2.Position.y)**2) + ((j1.Position.z - j2.Position.z)**2))


class BodyGameRuntime(object):
    def __init__(self, background_img, windowed_mode, show_pip):
        pygame.init()

        # Init pygame mixer and load each song in each channel
        pygame.mixer.init()
        pygame.mixer.set_num_channels(len(CRACK_SOUNDS))

        # This will be used to limits the number of cracks to max 2 per second
        self._can_punch = True

        # True means the user wants a PiP is shown on the bottom right
        self._show_pip = show_pip

        # Used to manage how fast the screen updates
        self._clock = pygame.time.Clock()

        # Set the width and height of the screen [width, height]
        self._infoObject = pygame.display.Info()

        if windowed_mode:
            self._screen = pygame.display.set_mode(
                (self._infoObject.current_w >> 1, self._infoObject.current_h >> 1),
                pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.RESIZABLE, 32)
        else:
            self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)

        pygame.display.set_caption("PyNoStress")

        # Used to manage how fast the screen updates
        self._clock = pygame.time.Clock()

        # Kinect runtime object, we want IR if show_pip, and body frames always
        if show_pip:
            self._kinect = PyKinectRuntime.PyKinectRuntime(
                PyKinectV2.FrameSourceTypes_Infrared | PyKinectV2.FrameSourceTypes_Body)
        else:
            self._kinect = PyKinectRuntime.PyKinectRuntime(PyKinectV2.FrameSourceTypes_Body)

        # init frame surface with screenshot
        self._background_img = background_img
        self._frame_surface = None
        self.set_surface_from_img(self._background_img)

        # backup original background image (useful to reset)
        self._orig_background_img = copy.deepcopy(background_img)

        # here we will store skeleton data
        self._bodies = None

        # Create variables to store last 3 hand positions...
        self._hl = []
        self._hr = []
        # ... and last hand velocities
        self._l_velocity = None
        self._r_velocity = None

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
        shoulders_length = dist(joint_shoulder_r, joint_neck) + dist(joint_shoulder_l, joint_neck) * 0.7
        neck_spine_length = dist(joint_neck, joint_spine) * 1.5

        l_arm_length = dist(joint_shoulder_l, joint_elbow_l) + dist(joint_elbow_l, joint_wrist_l)
        r_arm_length = dist(joint_shoulder_r, joint_elbow_r) + dist(joint_elbow_r, joint_wrist_r)

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
            new_hl_y = ((joint_hand_left.Position.y - neck_spine_m["y"]) * screen_h / neck_spine_length) + (screen_h/2)
            l_punch_coord = int(new_hl_x), int(new_hl_y)
            self.add_punch(l_punch_coord[0], l_punch_coord[1], alpha=alpha_dist_l)

        r_punch_coord = None
        if joints[PyKinectV2.JointType_HandRight].TrackingState != PyKinectV2.TrackingState_NotTracked:
            new_hr_x = ((joint_hand_right.Position.x - neck_spine_m["x"]) * screen_w / shoulders_length) + (screen_w/2)
            new_hr_y = ((joint_hand_right.Position.y - neck_spine_m["y"]) * screen_h / neck_spine_length) + (screen_h/2)
            r_punch_coord = int(new_hr_x), int(new_hr_y)
            self.add_punch(r_punch_coord[0], r_punch_coord[1], alpha=alpha_dist_r, flip=True)

        return l_punch_coord, r_punch_coord, alpha_dist_l == 255, alpha_dist_r == 255

    def add_crack(self, x, y, backup_img):
        # Add a new crack (if this possibility is enabled)
        if not self._can_punch:
            return

        crack = Image.open(random.choice(CRACK_PATHS))
        self._background_img.paste(crack, (x, y), crack)
        backup_img.paste(crack, (x, y), crack)

        # Play sound
        s = random.randint(0, len(CRACK_SOUNDS)-1)
        pygame.mixer.Channel(s).play(pygame.mixer.Sound(CRACK_SOUNDS[s]))

        self.disable_draw_punch()

    def add_punch(self, x, y, alpha=255, flip=False):
        # Draw the punch at specific location, with specific size and opacity based on alpha
        punch = Image.open(PUNCH_PATH)
        screen_w = self._screen.get_width()
        pip_w = int(screen_w * 0.15 * (0.5 + (alpha/150)))

        if pip_w <= 0:
            return

        punch.thumbnail([pip_w, sys.maxsize], Image.ANTIALIAS)

        pixels = punch.getdata()
        new_pixels = []
        for item in pixels:
            if item[3] < 200:
                new_pixels.append(item)
            else:
                new_pixels.append((item[0], item[1], item[2], alpha))
        punch.putdata(new_pixels)

        if flip:
            punch = ImageOps.mirror(punch)

        self._background_img.paste(punch, (x, y), punch)

    def add_pip(self):
        # add PiP
        f = self._kinect.get_last_infrared_frame()

        ir_f8 = np.uint8(f.clip(1, 4000) / 16.)
        ir_frame8bit = np.dstack((ir_f8, ir_f8, ir_f8))
        ir_rgb = np.array(ir_frame8bit)
        ir_rgb = ir_rgb.reshape((self._kinect.infrared_frame_desc.Height, self._kinect.infrared_frame_desc.Width, 3),
                                order='C')

        im_pil = Image.fromarray(ir_rgb).convert("RGBA")

        #Resize image to 10% width
        screen_w = self._frame_surface.get_width()
        screen_h = self._frame_surface.get_height()
        pip_w = int(screen_w * 0.1)
        im_pil.thumbnail([pip_w, sys.maxsize], Image.ANTIALIAS)
        pip_w, pip_h = im_pil.size

        self._background_img.paste(im_pil, (screen_w-pip_w-15, screen_h-pip_h-15), im_pil)

    def get_h_joints_acceleration(self, joints):
        # Compute hands joints acceleration
        self._hl.append(joints[PyKinectV2.JointType_HandLeft])
        self._hr.append(joints[PyKinectV2.JointType_HandRight])

        if len(self._hl) == 1:
            self._l_velocity = None
            l_acc = None
        elif len(self._hl) == 2:
            self._l_velocity = dist(self._hl[0], self._hl[1])
            l_acc = None
        elif len(self._hl) == 3:
            self._l_velocity = dist(self._hl[1], self._hl[2])
            l_acc = self._l_velocity - dist(self._hl[1], self._hl[0])
        else:
            del self._hl[0]
            self._l_velocity = dist(self._hl[1], self._hl[2])
            l_acc = self._l_velocity - dist(self._hl[1], self._hl[0])

        if len(self._hr) == 1:
            self._r_velocity = None
            r_acc = None
        elif len(self._hr) == 2:
            self._r_velocity = dist(self._hr[0], self._hr[1])
            r_acc = None
        elif len(self._hr) == 3:
            self._r_velocity = dist(self._hr[1], self._hr[2])
            r_acc = self._r_velocity - dist(self._hr[1], self._hr[0])
        else:
            del self._hr[0]
            self._r_velocity = dist(self._hr[1], self._hr[2])
            r_acc = self._r_velocity - dist(self._hr[1], self._hr[0])

        return l_acc, r_acc

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

            if self._kinect.has_new_body_frame():
                self._bodies = self._kinect.get_last_body_frame()
            else:
                self._bodies = None

            if self._show_pip and self._kinect.has_new_infrared_frame():
                self.add_pip()

            # Save background image before adding additional stuff
            background_img_before_punch = copy.deepcopy(self._background_img)

            if self._bodies is not None:
                for i in range(0, self._kinect.max_body_count):
                    body = self._bodies.bodies[i]
                    if not body.is_tracked:
                        continue

                    joints = body.joints

                    l_punch_coord, r_punch_coord, punched_l, punched_r = self.draw_punch(joints)
                    l_acc, r_acc = self.get_h_joints_acceleration(joints)

                    if punched_l and (l_acc is not None) and (l_acc > 0.05):
                        self.add_crack(*l_punch_coord, background_img_before_punch)
                    if punched_r and (r_acc is not None) and (r_acc > 0.05):
                        self.add_crack(*r_punch_coord, background_img_before_punch)

                    # No need to check for other bodies, use only one
                    break

                    # TODO automatic selection of nearest body

            # Prepare surface
            self.set_surface_from_img(self._background_img)
            h_to_w = float(self._frame_surface.get_height()) / self._frame_surface.get_width()
            target_height = int(h_to_w * self._screen.get_width())
            surface_to_draw = pygame.transform.scale(self._frame_surface, (self._screen.get_width(), target_height));
            self._screen.blit(surface_to_draw, (0, 0))
            surface_to_draw = None

            pygame.display.update()

            # update the screen with what we've drawn
            pygame.display.flip()

            # limit to 60 frames per second
            self._clock.tick(60)

            # Restore original background_image to what it was before drawing punches
            self._background_img = background_img_before_punch

        # Close our Kinect sensor, close the window and quit.
        self._kinect.close()
        pygame.quit()


def start_game(windowed_mode=False, show_pip=False):
    with mss.mss() as sct:
        sct_img = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    game = BodyGameRuntime(img, windowed_mode, show_pip)
    game.run()
