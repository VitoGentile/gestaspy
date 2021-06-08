from core.game import start_game


def main(args):
    start_game(windowed_mode=args.windowed, show_pip=args.pip, pip_size=args.pip_size[0])
