import argparse
from .collections import ChainMap
from pathlib import Path
from typing import Optional, Any, Union, List, Dict

import pydash
import yaml

from .utils import Singleton

try:
    from yaml import CLoader as YamlLoader
except ImportError:
    from yaml import Loader as YamlLoader


class Rc(Singleton):
    _dir_etc = Path('/etc')
    _dir_user_config = Path.home() / '.config'
    _conf = ChainMap()

    defaults = {}

    async def load(self, project_name: str, defaults: dict | None = None, fn_rc: Path | None = None):

        def _read_regular_files():
            ff = [
                self.__class__._dir_etc / project_name / 'rc.yaml',
                self.__class__._dir_user_config / project_name / 'rc.yaml',
                Path.cwd() / 'rc.yaml'
            ]
            if fn_rc:
                if not fn_rc.exists():
                    raise FileNotFoundError(f'Specified RC file not found: "{fn_rc}"')
                ff.append(Path(fn_rc))
            dd = []
            for fn in ff:
                if fn.exists():
                    with open(fn, 'rt', encoding='utf-8') as fp:
                        dd.append(yaml.load(fp, Loader=YamlLoader))
            dd.reverse()
            return dd

        def _read_secrets_file():
            fn = self.__class__._conf.get('secrets')
            if not fn:
                fn = Path.home() / (project_name + '.secrets.yaml')
                if not fn.exists():
                    return None
                with open(fn, 'rt', encoding='utf-8') as fp:
                    return yaml.load(fp, Loader=YamlLoader)

        if defaults is None:
            defaults = self.__class__.defaults
        self.__class__._conf = ChainMap(*reversed([defaults] + _read_regular_files()))
        secrets = _read_secrets_file()
        if secrets:
            self.__class__._conf = self.__class__._conf.new_child(secrets)

    def g(self, path: Union[str, List], default: Optional[Any] = None):
        return self.__class__._conf.get(path, default)

    def s(self, path, value):
        # noinspection PyTypeChecker
        # --> allow ChainMap to be used like Dict
        self.__class__._conf[path] = value

    def add_args(self, args: argparse.Namespace, new_child=True):
        self.__class__._conf = self.__class__._conf.new_child({k:v for k,v in vars(args).items() if v is not None})
        if new_child:
            self.__class__._conf = self.__class__._conf.new_child({})

    @property
    def conf(self):
        return self.__class__._conf
