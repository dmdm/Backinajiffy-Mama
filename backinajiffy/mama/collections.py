import _collections_abc

from pydash import py_


class ChainMapMissingKey:
    pass


class ChainMap(_collections_abc.MutableMapping):
    ''' A ChainMap groups multiple dicts (or other mappings) together
    to create a single, updateable view.

    The underlying mappings are stored in a list.  That list is public and can
    be accessed or updated using the *maps* attribute.  There is no other
    state.

    Lookups search the underlying mappings successively until a key is found.
    In contrast, writes, updates, and deletions only operate on the first
    mapping.

    '''

    def __init__(self, *maps: dict):
        '''Initialize a ChainMap by setting *maps* to the given mappings.
        If no mappings are provided, a single empty dictionary is used.

        '''
        self.maps = list(maps) or [{}]  # always at least one map

    def __missing__(self, key: str):
        raise KeyError(key)

    def __getitem__(self, key: str):
        key = key.replace('__', '.')
        for mapping in self.maps:
            v = py_.get(mapping, key, ChainMapMissingKey)
            if v != ChainMapMissingKey:
                return v
        else:
            return self.__missing__(key)

    def get(self, key, default=None):
        key = key.replace('__', '.')
        for mapping in self.maps:
            v = py_.get(mapping, key, ChainMapMissingKey)
            if v != ChainMapMissingKey:
                return v
        else:
            return default

    def __len__(self):
        return len(set().union(*self.maps))

    def __iter__(self):
        d = {}
        for mapping in reversed(self.maps):
            d.update(dict.fromkeys(mapping))
        return iter(d)

    def __contains__(self, key):
        key = key.replace('__', '.')
        for mapping in self.maps:
            b = py_.has(mapping, key)
            if b:
                return True
        else:
            return False

    def __bool__(self):
        return any(self.maps)

    def __repr__(self):
        return f'{self.__class__.__name__}({", ".join(map(repr, self.maps))})'

    @classmethod
    def fromkeys(cls, iterable, *args):
        'Create a ChainMap with a single dict created from the iterable.'
        return cls(dict.fromkeys(iterable, *args))

    def copy(self):
        'New ChainMap or subclass with a new copy of maps[0] and refs to maps[1:]'
        return self.__class__(self.maps[0].copy(), *self.maps[1:])

    __copy__ = copy

    def new_child(self, m=None, **kwargs):  # like Django's Context.push()
        '''New ChainMap with a new map followed by all previous maps.
        If no map is provided, an empty dict is used.
        Keyword arguments update the map or new empty dict.
        '''
        if m is None:
            m = kwargs
        elif kwargs:
            m.update(kwargs)
        return self.__class__(m, *self.maps)

    @property
    def parents(self):  # like Django's Context.pop()
        'New ChainMap from maps[1:].'
        return self.__class__(*self.maps[1:])

    def __setitem__(self, key, value):
        py_.set(self.maps[0], key, value)

    def __delitem__(self, key):
        try:
            py_.delete(self.maps[0], key)
        except KeyError:
            raise KeyError(f'Key not found in the first mapping: {key!r}')

    def popitem(self):
        'Remove and return an item pair from maps[0]. Raise KeyError is maps[0] is empty.'
        try:
            return self.maps[0].popitem()
        except KeyError:
            raise KeyError('No keys found in the first mapping.')

    def pop(self, key, *args):
        'Remove *key* from maps[0] and return its value. Raise KeyError if *key* not in maps[0].'
        try:
            return self.maps[0].pop(key, *args)
        except KeyError:
            raise KeyError(f'Key not found in the first mapping: {key!r}')

    def clear(self):
        'Clear maps[0], leaving maps[1:] intact.'
        self.maps[0].clear()

    def __ior__(self, other):
        self.maps[0].update(other)
        return self

    def __or__(self, other):
        if not isinstance(other, _collections_abc.Mapping):
            return NotImplemented
        m = self.copy()
        m.maps[0].update(other)
        return m

    def __ror__(self, other):
        if not isinstance(other, _collections_abc.Mapping):
            return NotImplemented
        m = dict(other)
        for child in reversed(self.maps):
            m.update(child)
        return self.__class__(m)
