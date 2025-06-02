import asyncio
from concurrent.futures import ThreadPoolExecutor
from inspect import isclass
from types import UnionType
from typing import (
    Any,
    Awaitable,
    Callable,
    List,
    Optional,
    ParamSpec,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

from asgiref.sync import async_to_sync
from flask import current_app, request
from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic.json_schema import GetJsonSchemaHandler, JsonSchemaValue
from pydantic_core import CoreSchema, PydanticCustomError, core_schema
from werkzeug.datastructures import FileStorage


class UploadedFile(FileStorage):
    """A pydantic custom type wrapper for uploaded file streams in Flask/Werkzeug"""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_before_validator_function(
            cls.validate, core_schema.AnySchema(type="any")
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.JsonSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema.update(type="string", format="binary")
        return json_schema

    @classmethod
    def validate(cls, value: Any) -> FileStorage:
        if not isinstance(value, FileStorage):
            raise PydanticCustomError("file_type", "file required")
        return value


_UNION_TYPES = {Union, UnionType}


def is_union(value: Any) -> bool:
    return get_origin(value) in _UNION_TYPES


def is_union_of_model_sublclasses(value: Any) -> bool:
    if not is_union(value):
        return False

    return all([isclass(v) and issubclass(v, BaseModel) for v in get_args(value)])


def get_annotated_models(
    func: Callable,
) -> Tuple[
    Optional[str], Optional[List[Type[BaseModel]]], Optional[List[Type[BaseModel]]]
]:
    request_models = None
    request_model_param_name = None
    response_models = None

    view_model_args = [
        k
        for k, v in func.__annotations__.items()
        if v
        and k != "return"
        and (
            (isclass(v) and issubclass(v, BaseModel))
            or is_union_of_model_sublclasses(v)
        )
    ]

    if len(view_model_args) > 1:
        raise Exception(
            f"Too many model arguments specified for {func.__name__}. "
            "Could not determine which to map to request body"
        )
    elif len(view_model_args) == 1 and (
        request_annotation := func.__annotations__.get(view_model_args[0])
    ):
        request_model_param_name = view_model_args[0]
        if is_union(request_annotation):
            request_models = [
                annotation
                for annotation in get_args(request_annotation)
                if isclass(annotation) and issubclass(annotation, BaseModel)
            ]

        elif isclass(request_annotation) and issubclass(request_annotation, BaseModel):
            request_models = [request_annotation]

    return_annotation = func.__annotations__.get("return")
    if return_annotation:
        if is_union(return_annotation):
            response_models = [
                annotation
                for annotation in get_args(return_annotation)
                if isclass(annotation) and issubclass(annotation, BaseModel)
            ]

        elif isclass(return_annotation) and issubclass(return_annotation, BaseModel):
            response_models = [return_annotation]

    return request_model_param_name, request_models, response_models


def function_has_fields_in_signature(func: Callable, request_fields_name: str) -> bool:
    return request_fields_name in func.__annotations__


def model_has_uploaded_file_type(model: Type[BaseModel]) -> bool:
    for field in model.model_fields.values():
        if field.annotation == UploadedFile:
            return True

    return False


executor = ThreadPoolExecutor(max_workers=4)

P = ParamSpec("P")
T = TypeVar("T")


def sync_async_wrapper(
    func: Callable[P, T | Awaitable[T]], *args: P.args, **kwargs: P.kwargs
) -> T:
    if not asyncio.iscoroutinefunction(func):
        return cast(T, func(*args, **kwargs))

    try:
        return cast(T, async_to_sync(func)(*args, **kwargs))
    except RuntimeError:
        # This means there is already a running event loop.  The only way forward
        # is to run in a separate thread with a new event_loop.  This is complicated
        # by the need to replicate Flask app and request context vars in the new thread.

        def sync_runner():
            app = current_app._get_current_object()  # type: ignore
            req_context = request._get_current_object()  # type: ignore

            def run_in_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:

                    async def run_async_with_context():
                        with app.app_context():
                            with app.request_context(req_context.environ):
                                return cast(T, await func(*args, **kwargs))

                    return loop.run_until_complete(run_async_with_context())
                finally:
                    loop.close()

            return executor.submit(run_in_thread).result()

        return sync_runner()


def unindent_text(text: str) -> str:
    """Strip leading and trailing lines from the given text and then as much leading
    unindent as possible from the whole block.
    """
    lines = text.splitlines()
    lines = [ln.rstrip() for ln in lines]
    while lines and (not lines[0] or lines[0].isspace()):
        lines = lines[1:]
    while lines and (not lines[-1] or lines[-1].isspace()):
        lines = lines[:-1]

    indent = min(len(ln) - len(ln.lstrip()) for ln in lines if ln) if lines else 0
    if indent:
        lines = [line[indent:] for line in lines]

    return "\n".join(lines)
