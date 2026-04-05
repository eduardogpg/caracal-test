from typing import Any, Optional, TypeAlias, List, Callable, Tuple, Dict
from dataclasses import dataclass
from collections import defaultdict
from contextlib import contextmanager

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
    _context_skip_callbacks: set[str] = set()

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

    def _get_callbacks_by_stage(self, stage: Stage) -> List[Callback]:
        registered_callbacks: StageCallbacks = self._get_registered_callbacks()
        return registered_callbacks.get(stage, [])

    def _should_run_callback(self, callback: Callback) -> bool:
        options: dict[str, Any] = callback.kwargs or {}

        if "skip" in options:
            return False

        return True

    @contextmanager
    def skip_hooks(self, *method_names: str):
        """
        Temporarily disable specific callbacks for this model instance.
        """
        previous = set(getattr(self, "_context_skip_callbacks", set()))
        self._context_skip_callbacks = previous | set(method_names)
        try:
            yield self
        finally:
            self._context_skip_callbacks = previous

    def run_callbacks(
        self,
        stage: Stage,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        callbacks_to_run: List[Callback] = []

        for callback in self._get_callbacks_by_stage(stage):
            method_name = getattr(callback.callback, "__name__", None)

            if not method_name:
                raise TypeError("Registered callback must have a method name.")

            if not self._should_run_callback(callback):
                continue

            callbacks_to_run.append(callback)

        for callback in callbacks_to_run:
            callback.callback(*args, **kwargs)


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
        update_fields: Optional[list[str] | tuple[str, ...] | set[str]] = kwargs.get("update_fields")
        validate_exclude: Optional[list[str]] = self._build_validate_exclude(
            validate_exclude=validate_exclude,
            update_fields=update_fields,
        )

        if validate:
            self.full_clean(
                exclude=validate_exclude,
                validate_unique=validate_unique,
                validate_constraints=validate_constraints,
            )

        is_create: bool = self.pk is None
        is_update: bool = not is_create

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
