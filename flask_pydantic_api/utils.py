from inspect import isclass
from typing import (
    Any,
    Callable,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
)

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


def get_annotated_models(
    func: Callable,
) -> Tuple[Optional[str], Optional[Type[BaseModel]], Optional[List[Type[BaseModel]]]]:
    request_model = None
    request_model_param_name = None
    response_models = None

    view_model_args = [
        k
        for k, v in func.__annotations__.items()
        if v and k != "return" and isclass(v) and issubclass(v, BaseModel)
    ]

    if len(view_model_args) > 1:
        raise Exception(
            f"Too many model arguments specified for {func.__name__}. "
            "Could not determine which to map to request body"
        )
    elif len(view_model_args) == 1:
        request_model_param_name = view_model_args[0]
        request_model = func.__annotations__[request_model_param_name]

    return_annotation = func.__annotations__.get("return")
    if not return_annotation:
        return request_model_param_name, request_model, response_models

    if get_origin(return_annotation) == Union:
        response_models = [
            annotation
            for annotation in get_args(return_annotation)
            if isclass(annotation) and issubclass(annotation, BaseModel)
        ]

    elif isclass(return_annotation) and issubclass(return_annotation, BaseModel):
        response_models = [return_annotation]

    return request_model_param_name, request_model, response_models


def function_has_fields_in_signature(func: Callable, request_fields_name: str) -> bool:
    return request_fields_name in func.__annotations__


def model_has_uploaded_file_type(model: Type[BaseModel]) -> bool:
    for field in model.model_fields.values():
        if field.annotation == UploadedFile:
            return True

    return False
