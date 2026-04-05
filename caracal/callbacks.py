from typing import Callable
from caracal.constants import (
    BEFORE_SAVE, AFTER_SAVE, BEFORE_CREATE, AFTER_CREATE,
    BEFORE_UPDATE, AFTER_UPDATE, BEFORE_DELETE, AFTER_DELETE,
    BEFORE_COMMIT, AFTER_COMMIT
)


def model_callback(stage, *callback_args, **callback_kwargs):
    def wrapper(function: Callable):
        function._model_callback: bool = True
        function._model_callback_stage: str = stage

        return function

    # Supports both:
    # @before_save
    # @before_save(...)
    if (
        len(callback_args) == 1
        and callable(callback_args[0])
        and not callback_kwargs
    ):
        return wrapper(callback_args[0])

    return wrapper


def before_save(*args, **kwargs) -> Callable:
    return model_callback(BEFORE_SAVE, *args, **kwargs)


def after_save(*args, **kwargs) -> Callable:
    return model_callback(AFTER_SAVE, *args, **kwargs)


def before_create(*args, **kwargs) -> Callable:
    return model_callback(BEFORE_CREATE, *args, **kwargs)


def after_create(*args, **kwargs) -> Callable:
    return model_callback(AFTER_CREATE, *args, **kwargs)


def before_update(*args, **kwargs) -> Callable:
    return model_callback(BEFORE_UPDATE, *args, **kwargs)


def after_update(*args, **kwargs) -> Callable:
    return model_callback(AFTER_UPDATE, *args, **kwargs)


def before_commit(*args, **kwargs) -> Callable:
    return model_callback(BEFORE_COMMIT, *args, **kwargs)


def after_commit(*args, **kwargs) -> Callable:
    return model_callback(AFTER_COMMIT, *args, **kwargs)


def before_delete(*args, **kwargs) -> Callable:
    return model_callback(BEFORE_DELETE, *args, **kwargs)


def after_delete(*args, **kwargs) -> Callable:
    return model_callback(AFTER_DELETE, *args, **kwargs)