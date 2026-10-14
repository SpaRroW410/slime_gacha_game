"""Domain errors. The CLI catches GameError and prints the message."""


class GameError(Exception):
    pass


class NotEnoughResources(GameError):
    pass


class InvalidAction(GameError):
    pass
