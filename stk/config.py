
from os import path
from yaml import safe_load
class ConfigFile(dict):
  EXPECTED_KEYS = ['vars', 'params', 'environments']
  def __init__(self, filename: str):
    self.filename = filename

    self['vars'] = {}
    self['params'] = {}

    cfg = safe_load(open(filename)) or dict()
    super().__init__(cfg)
    self._ensure_valid_keys()

  def _ensure_valid_keys(self):
    """
    Ensure config file only contains expected keys
    """
    unknown_keys = set(self.keys()) - set(self.EXPECTED_KEYS)

    if unknown_keys:
      raise Exception(f"Config file {self.filename} has unexpected keys: {unknown_keys}")



class Config:
  def __init__(self, name: str, environment: str, config_path: str, var_overrides: dict = {}, param_overrides: dict = {}):
    self.name = name
    self.environment = environment
    self.config_path = config_path

    self.cfg = ConfigFile(path.join(config_path, name + '.yml'))

  def vars(self):
    return self.cfg['vars']

  def params(self):
    return self.cfg['params']