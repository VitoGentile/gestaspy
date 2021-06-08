import argparse
from core.__main__ import main

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start gestaspy game')
    parser.add_argument("-w", "--windowed", help='start in windowed mode (useful for debugging)',
                        required=False,
                        default=False,
                        action='store_true')
    parser.add_argument("-p", "--pip", help='show PiP',
                        required=False,
                        default=False,
                        action='store_true')
    parser.add_argument("-s", "--pip-size", help='set PiP size as percentage of screen width (default 0.2)',
                        required=False,
                        default=[0.1],
                        nargs=1,
                        type=float)

    main(parser.parse_args())
