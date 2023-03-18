from inspect import isclass
from typing import Callable, List, Optional, Tuple, Type, Union, get_args, get_origin

from pydantic import BaseModel


def get_annotated_models(
    func: Callable,
) -> Tuple[Optional[str], Optional[Type[BaseModel]], Optional[List[Type[BaseModel]]]]:
    request_model = None
    request_model_param_name = None
    response_models = None

    view_model_args = [
        k
        for k, v in func.__annotations__.items()
        if v and k != "return" and issubclass(v, BaseModel)
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
            type_
            for type_ in get_args(return_annotation)
            if isclass(type_) and issubclass(type_, BaseModel)
        ]

    elif isclass(return_annotation) and issubclass(return_annotation, BaseModel):
        response_models = [return_annotation]

    return request_model_param_name, request_model, response_models
