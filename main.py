import argparse
from core import start_game

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start PyNoStress game')
    parser.add_argument("-w", "--windowed", help='start in windowed mode (useful for debugging)', required=False, default=False, action='store_true')
    parser.add_argument("-p", "--pip", help='show infrared PiP', required=False, default=False, action='store_true')

    args = parser.parse_args()

    start_game(windowed_mode=args.windowed, show_pip=args.pip)
