import yaml

from backinajiffy.mama.logging import CONFIG_LOGGING

if __name__ == '__main__':
    with open('logging.yaml', 'wt', encoding='utf-8') as fp:
        yaml.dump(CONFIG_LOGGING, fp)
