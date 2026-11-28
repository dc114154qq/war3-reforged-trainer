"""Product metadata, shared without loading UI or game backends."""
APP_VERSION = "2.2.8"
APP_RELEASE_CHANNEL = "stable"
GAME_BUILD = "3.0.0.24268"
PRODUCT_READ_MODE = "normal"
PRODUCT_EDITION_LABEL = "普通读取版"
WIN10_COMPAT_REVISION = "2.2.8-random-equipment-20261128"


def trainer_window_title(language='zh'):
    if language == 'en':
        return f'Warcraft III Reforged Trainer v{APP_VERSION} by Bilibili Two Cups of Shen Mengxi, ChatGPT and Claude'
    return f'魔兽争霸 III 修改器 v{APP_VERSION} by B站两杯沈梦溪、chatgpt和claude'
