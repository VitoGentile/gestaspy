import copy
import glob
import mss
import os
import pygame
import random
import sys
from PIL import Image, ImageOps
from threading import Timer

from core.device_manager import HandJointsFrame
from core.kinect_manager import KinectManager


def resource_path(relative_path=""):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

    return os.path.join(base_path, relative_path)


CRACK_PATHS = glob.glob(os.path.join(resource_path(), "assets", "cracks", "*.png"))
PUNCH_PATH = resource_path(os.path.join("assets", "punch.png"))
CRACK_SOUNDS = glob.glob(os.path.join(resource_path(), "assets", "audio", "*.wav"))


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

        # Kinect Device Manager
        self._kinect = KinectManager()
        self._kinect.start_device()
        self._kinect.set_filter_parameters(n=4)

        # init frame surface with screenshot
        self._background_img = background_img
        self._frame_surface = None
        self.set_surface_from_img(self._background_img)

        # backup original background image (useful to reset)
        self._orig_background_img = copy.deepcopy(background_img)

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

    def draw_punch(self, joints: HandJointsFrame):
        # Draw punch
        screen_w = self._frame_surface.get_width()
        screen_h = self._frame_surface.get_height()

        hjs = joints.get_hand_joints()

        # Compute alpha value, will be used for both opacity and puch size
        alpha_dist = dict()
        punch_coord = dict()
        for side in {"l", "r"}:
            if (hjs is None) or (hjs[side] is None):
                alpha_dist[side] = None
                punch_coord[side] = None
                continue

            alpha_dist[side] = 255 * hjs[side]["z"] * 1.5

            alpha_dist[side] = 0 if alpha_dist[side] < 0 else int(alpha_dist[side])
            alpha_dist[side] = 255 if alpha_dist[side] > 255 else int(alpha_dist[side])

            new_hl_x = (hjs[side]["x"] * screen_w) + (screen_w / 2)
            new_hl_y = -(hjs[side]["y"] * screen_h) + (screen_h / 2)
            punch_coord[side] = int(new_hl_x), int(new_hl_y)

            self.add_punch(side, punch_coord[side], alpha=alpha_dist[side])

        return punch_coord["l"], punch_coord["r"], alpha_dist["l"] == 255, alpha_dist["r"] == 255

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

    def add_punch(self, side, coord, alpha=255):
        # Draw the punch at specific location, with specific size and opacity based on alpha
        punch = Image.open(PUNCH_PATH)
        screen_w = self._frame_surface.get_width()
        punch_w = int(screen_w * 0.1 * ((0.2 + (alpha/170))**1.8))

        if punch_w <= 0:
            return

        punch.thumbnail([punch_w, sys.maxsize], Image.ANTIALIAS)

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

        self._background_img.paste(punch, coord, punch)

    def add_pip(self):
        # add PiP
        f = self._kinect.get_last_color_frame()
        if f is None:
            return

        im_pil = f.get_img()

        # Resize image to 10% width
        screen_w = self._frame_surface.get_width()
        screen_h = self._frame_surface.get_height()
        pip_w = int(screen_w * 0.1)
        im_pil.thumbnail([pip_w, sys.maxsize], Image.ANTIALIAS)
        pip_w, pip_h = im_pil.size

        self._background_img.paste(im_pil, (screen_w-pip_w-15, screen_h-pip_h-15), im_pil)

    def run(self):
        # Main Program Loop

        last_hf = None
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

            if self._show_pip:
                self.add_pip()

            # Save background image before adding additional stuff
            background_img_before_punch = copy.deepcopy(self._background_img)

            hand_joints_frame = self._kinect.get_last_hand_joints_frame()
            if (hand_joints_frame is not None) and hand_joints_frame != last_hf:
                last_hf = hand_joints_frame

                l_punch_coord, r_punch_coord, punched_l, punched_r = self.draw_punch(hand_joints_frame)
                l_acc, r_acc = self._kinect.get_hand_joints_velocities()

                if punched_l and (l_acc is not None) and (l_acc > 0.4):
                    self.add_crack(*l_punch_coord, background_img_before_punch)
                if punched_r and (r_acc is not None) and (r_acc > 0.4):
                    self.add_crack(*r_punch_coord, background_img_before_punch)

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
        self._kinect.stop_device()
        pygame.quit()


def start_game(windowed_mode=False, show_pip=False):
    with mss.mss() as sct:
        sct_img = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    game = BodyGameRuntime(img, windowed_mode, show_pip)
    game.run()
