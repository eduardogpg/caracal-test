from typing import Any, Optional, TypeAlias, List, Callable, Tuple, Dict
from dataclasses import dataclass
from collections import defaultdict

from django.db import models
from django.db import transaction


@dataclass(frozen=True)
class Callback:
    callback: Callable[..., Any]
    args: Optional[Tuple[Any, ...]] = None
    kwargs: Optional[dict[str, Any]] = None


Stage: TypeAlias = str
StageCallbacks: TypeAlias = dict[Stage, List[Callback]]


class CallbackRegisterModel:
    _registered_callbacks: StageCallbacks = {}

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls._collect_registered_callbacks()

    @classmethod
    def _collect_registered_callbacks(cls) -> None:
        """
        Collects registered callbacks from the class hierarchy.

        Grouping callbacks by stage.

        e.g
        {
            "before_save": [
                {
                    "callback": <callback function>,
                }
            ]
            "after_save": [
                {
                    "callback": <callback function>,
                },
                {
                    "callback": <callback function>,
                },
            ]
        }
        """
        callbacks: Dict[Stage, List[Callback]] = defaultdict(list)

        for base in reversed(cls.__mro__):
            for attr_name, attr_value in base.__dict__.items():
                if not callable(attr_value):
                    continue

                if not getattr(attr_value, "_model_callback", False):
                    continue

                stage: Optional[Stage] = getattr(
                    attr_value, "_model_callback_stage", None
                )

                if not stage:
                    continue

                callback = Callback(
                    callback=attr_value,
                    args=getattr(attr_value, "_model_callback_args", None),
                    kwargs=getattr(attr_value, "_model_callback_options", None)
                )

                callbacks[stage].append(callback)

        cls._registered_callbacks: StageCallbacks = callbacks

    def _get_registered_callbacks(self) -> StageCallbacks:
        cls: type[CallbackRegisterModel] = self.__class__

        if not getattr(cls, "_registered_callbacks", None):
            cls._collect_registered_callbacks()

        return cls._registered_callbacks

    def run_callbacks(self, stage: Stage, *args: Any, **kwargs: Any) -> None:
        registered_callbacks: StageCallbacks = self._get_registered_callbacks()

        callbacks: List[Callback] = registered_callbacks.get(stage, [])

        for callback in callbacks:
            method_name = getattr(callback.callback, "__name__", None)

            if not method_name:
                raise TypeError("Registered callback must have a method name.")

            method = getattr(self, method_name)
            method(*args, **kwargs)


class LifeCycleModel(CallbackRegisterModel, models.Model):
    class Meta:
        abstract = True

    def _build_validate_exclude(
        self,
        validate_exclude: Optional[list[str]],
        update_fields: Optional[list[str] | tuple[str, ...] | set[str]],
    ) -> Optional[list[str]]:
        if validate_exclude is not None:
            return validate_exclude

        if update_fields is None:
            return None

        allowed_fields = set(update_fields)
        return [
            field.name
            for field in self._meta.fields
            if field.name not in allowed_fields
        ]

    def save(self, *args, **kwargs) -> None:
        validate: bool = kwargs.pop("validate", True)
        validate_unique: bool = kwargs.pop("validate_unique", True)
        validate_constraints: bool = kwargs.pop("validate_constraints", True)
        validate_exclude: Optional[list[str]] = kwargs.pop("validate_exclude", None)
        update_fields = kwargs.get("update_fields")
        validate_exclude = self._build_validate_exclude(
            validate_exclude=validate_exclude,
            update_fields=update_fields,
        )

        is_create: bool = self.pk is None
        is_update: bool = not is_create

        if validate:
            self.full_clean(
                exclude=validate_exclude,
                validate_unique=validate_unique,
                validate_constraints=validate_constraints,
            )

        with transaction.atomic():
            self.run_callbacks("before_save", *args, **kwargs)

            if is_create:
                self.run_callbacks("before_create", *args, **kwargs)
            elif is_update:
                self.run_callbacks("before_update", *args, **kwargs)

            super().save(*args, **kwargs)

            if is_create:
                self.run_callbacks("after_create", *args, **kwargs)
            elif is_update:
                self.run_callbacks("after_update", *args, **kwargs)

        transaction.on_commit(
            lambda: self.run_callbacks("after_commit", *args, **kwargs)
        )

    def delete(self, *args, **kwargs) -> None:
        with transaction.atomic():
            self.run_callbacks("before_delete", *args, **kwargs)

            super().delete(*args, **kwargs)

            self.run_callbacks("after_delete", *args, **kwargs)

        transaction.on_commit(
            lambda: self.run_callbacks("after_commit", *args, **kwargs)
        )
