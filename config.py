# config.py
""" write/read parameters from a JSON file """

import json
import os


def write_cf(filename, data):
    """ write dict as json config file """
    with open(filename, 'w') as f:
        json.dump(data, f)


def read_cf(filename, default=None):
    """ return json file as dict or write default """
    if filename in os.listdir():
        with open(filename, 'r') as f:
            data = json.load(f)
        return data
    elif default:
        print(f'Write default values to: {filename}')
        write_cf(filename, default)
        return default


def pc_u16(percentage):
    """ convert positive percentage to 16-bit equivalent """
    if 0 < percentage <= 100:
        return 0xffff * percentage // 100
    else:
        return 0
