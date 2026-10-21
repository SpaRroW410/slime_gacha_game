"""Domain errors. The CLI catches GameError and prints the message."""


class GameError(Exception):
    pass


class SaveError(GameError):
    """A save file that cannot be loaded (damaged, not a save, or from a newer version)."""


class NotEnoughResources(GameError):
    pass


class InvalidAction(GameError):
    pass
