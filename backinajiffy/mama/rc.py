import argparse
from collections import ChainMap
from pathlib import Path
from typing import Optional, Any, Union, List, Dict

import pydash
import yaml

try:
    from yaml import CLoader as YamlLoader
except ImportError:
    from yaml import Loader as YamlLoader


class Rc:
    _instance = None
    _dir_etc = Path('/etc')
    _dir_user_config = Path.home() / '.config'
    _conf = ChainMap()

    defaults = {}

    @classmethod
    def create(cls, project_name: str, defaults: Optional[Dict] = None, fn_rc: Optional[Path] = None) -> 'Rc':

        def _read_regular_files():
            ff = [
                cls._dir_etc / project_name / 'rc.yaml',
                cls._dir_user_config / project_name / 'rc.yaml',
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
                        dd.append(flatten(yaml.load(fp, Loader=YamlLoader)))
            dd.reverse()
            return dd

        def _read_secrets_file():
            fn = cls._conf.get('secrets')
            if not fn:
                fn = Path.home() / (project_name + '.secrets.yaml')
                if not fn.exists():
                    return None
                with open(fn, 'rt', encoding='utf-8') as fp:
                    return yaml.load(fp, Loader=YamlLoader)

        if defaults is None:
            defaults = cls.defaults
        cls._instance = Rc()
        cls._conf = ChainMap(*reversed([defaults] + _read_regular_files()))
        secrets = _read_secrets_file()
        if secrets:
            cls._conf = cls._conf.new_child(flatten(secrets))
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'Rc':
        if not cls._instance:
            raise ValueError('Instance of RC has not been created yet. Call Rc.create() first.')
        return cls._instance

    def __init__(self):
        pass

    def g(self, path: Union[str, List], default: Optional[Any] = None):
        return self.__class__._conf.get(path, default)
        # return pydash.get(self.__class__._conf, path, default)

    def s(self, path, value):
        # noinspection PyTypeChecker
        # --> allow ChainMap to be used like Dict
        self.__class__._conf[path] = value
        # pydash.set_(self.__class__._conf, path, value)

    def gg(self, path: Union[str, List], default: Optional[Any] = None):
        conf = self.__class__._conf
        kk = [k for k in conf.keys() if k.startswith(path)]
        return {k[len(path + '.'):]: conf[k] for k in kk}

    def add_args(self, args: argparse.Namespace, new_child=True):
        self.__class__._conf = self.__class__._conf.new_child({k:v for k,v in vars(args).items() if v is not None})
        if new_child:
            self.__class__._conf = self.__class__._conf.new_child({})


    @property
    def conf(self):
        return self.__class__._conf


def flatten(d: Dict, sep='.') -> Dict:
    def _f(d: Dict, z: Dict, p: str):
        for k, v in d.items():
            np = p + sep + k if p else k
            if isinstance(v, dict):
                _f(v, z, np)
            else:
                z[np] = v

    z = {}
    _f(d, z, '')
    return z
