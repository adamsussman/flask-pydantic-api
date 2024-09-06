# Flask Pydantic API

A wrapper for flask methods allowing them to use Pydantic argment and response types.

## Features

1. Use pydantic models for request data validation (post bodies and query strings) as well as for formatting responses
2. Type annotation driven on the view function instead of the decorator.
3. OpenAPI schema generation and documentation
4. Smart response fields and expansions using [pydantic-enhanced-serializer](https://github.com/adamsussman/pydantic-enhanced-serializer).
5. Fold path parameters into input Pydantic models
6. File Uploads into Pydantic model fields
7. Async views

## Installation

```console
$ pip install flask-pydantic-api
```

With support for [pydantic-enhanced-serializer](https://github.com/adamsussman/pydantic-enhanced-serializer):

```console
$ pip install flask-pydantic-api[serializer]
```

## Basic Usage

```python

    from flask import Flask
    from flask_pydantic_api import pydantic_api
    from pydantic import BaseModel

    app = Flask("my_app")


    class RequestBody(BaseModel):
        field1: str
        field2: Optional[int]


    class ResponseBody(BaseModel):
        response_field1: str


    # GET with query string field1=...&field2=..., responding with json RequestBody
    @app.get("/api/something")
    @pydantic_api(
        name="Go get something",        # Name of path operation in OpenAPI schema
        tags=["MyTag"],                 # OpenAPI tags
    )
    def do_work(body: RequestBody) -> ResponseBody:
        return ResponseBody(....)


    # POST with body
    @app.post("/api/something_else")
    @pydantic_api(
        name="Go do something",        # Name of path operation in OpenAPI schema
        tags=["MyTag"],                # OpenAPI tags
    )
    def do_work_post(body: RequestBody) -> ResponseBody:
        return ResponseBody(....)

    # Get direct access to request `fields` in work function
    # POST with body
    @app.post("/api/something_else")
    @pydantic_api(
        name="Go do something",        # Name of path operation in OpenAPI schema
        tags=["MyTag"],                # OpenAPI tags
    )
    def do_work_post(body: RequestBody, fields: List[str]) -> ResponseBody:
        fields = [list of request fields]
        return ResponseBody(....)

```

## OpenAPI

This library will generate the openapi.json schema to go with your usage of `@pydantic_api`.  An example
view is provided to serve it using [RapiDoc](https://rapidocweb.com/), but you can use any other openapi
viewer you wish.

```python

    from flask_pydantic_api import apidocs_views

    app = Flask("my_app")

    # GET /apidocs will render the rapidoc viewer
    # GET /apidocs/openapi.json will render the OpenAPI schema
    app.register_blueprint(apidocs_views.blueprint, url_prefix="/apidocs")
```

Note that you may wish to customize your schema results more than this module provides.  In that case:

```python

    from flask_pydantic_api.openapi import get_openapi_schema

    @app.get("/path/openapi.json")
    def get_openapi_schema() -> str:
        # param Info: from openapi_schema_pydantic
        # returns: openapi_schema_pydantic.OpenAPI
        my_schema = get_openapi_schema(info)

        # customize my_schema as wanted...

        return make_response(
            (
                my_schema.json(by_alias=True, exclude_none=True, indent=2),
                {"content-type": "application/json"},
            )
        )
```

## Configuration and Parameters

`@pydantic_api` accepts the following parameters:

* `name`: str - Name for this operation that will be used in the OpenAPI schema
* `Tags`: List[str] - Tags that will be used for this operation in the OpenAPI schema
* `success_status_code`: int = 200 - HTTP Status code that will be used on successful response
* `success_status_code_by_response_model`: Dict[Type[BaseModel], int] = None - If the return type of the method is a Union of multiple BaseModels, this dict can map those models to specific status codes
* `merge_path_parameters`: bool = False - See [Path Parameter Folding](#patharguments)
* `request_fields_name`: str = "fields" - If using `pydantic-enhanced-serialzer` this is the name of the request parameter that controls the fieldsets returned. See [Using the Enhanced Serializer](#serializer).
* `maximum_expansion_depth`: int = 5 - If using `pydantic-enhanced-serialzer` this controls how deep expansions can go. See [Using the Enhanced Serializer](#serializer).
* `openapi_schema_extra`: Optional[Dict[str, Any]] - Optional extra data to add to the openapi schema.  Will be merged with automatically generated schema data at `paths.<path>.<method>`.
* `model_dump_kwargs`: Optional[Dict[str, Any]] - Optional kwargs will be passed to Pydantic's `model_dump` as arguments when serializing a BaseModel returned by this endpoint.
* `get_request_model_from_query_string`: Optional[bool] - Affects OpenAPI schema generation.  When true the endpoint will specfify the request model's properties as query string arguments instead of request body arguments.  Defaults to False.

Flask configuration:

* `FLASK_PYDANTIC_API_RENDER_ERRORS`: bool = True.  If true, pydantic validation errors will be rendered to json and returned as a normal response.  If false, pydantic errors will yield a standard ValidationError exception.
* `FLASK_PYDANTIC_API_ERROR_STATUS_CODE`: int = 400.  If `FLASK_PYDANTIC_API_RENDER_ERRORS` is true, this is the HTTP status code that will be returned.

<a name="patharguments"></a>
## Path Parameter Folding

For paths that include parameters, you can request that the path parameters be moved into the pydantic
object for the request body.  In this case you will no longer need the parameter as an argument to
your view function.

* Use the `merge_path_parameters` argument to `@pydantic_api` to control this.
* For this to work, a field of the same name must exist in the request body model

```python
    # Normally...
    class RequestBodyNormal(BaseModel):
        field1: str

    @app.post("/path/<path_param1>/whatever")
    @pydantic_api()
    def do_work(path_param1: str, body: RequestBody) -> Response:
        path_param1 = "whatever was in path"
        ...
```

```python
    # With merging:
    class RequestBodyNormal(BaseModel):
        path_param1: str    # path_param1 is now here INSTEAD of the do_work signature
        field1: str

    @app.post("/path/<path_param1>/whatever")
    @pydantic_api(merge_path_parameters=True)
    def do_work(body: RequestBody) -> Response:
        body.path_param1  # use this instead of the function arg
        ...
```

## Response Object Flexibility

When returning from an api view, you will typically instantiate a populated response model and return that.

You can also return a dict, which will be cast into the response model.

You can also return any other object that Flask can handle.

```python

    class MyResponseModel(BaseModel):
        field1: str
        field2: int

    # returning a model instance
    @app.get("/")
    @pydantic_api()
    def do_work() -> MyResponseModel:
        ...
        model = MyResponseModel(field1="foo", field2=1234)
        return model

    # Returning a dict that is expected to be compliant with MyResponseModel:
    #   To make mypy happy, you need to indicate a dict return, but for the
    #   OpenAPI schema to work, you also need to specify the model.  Make
    #   both happy with a Union return type.
    #
    # NOTE: if the dict fails validation with MyResponseModel, the result
    # will be a 500 server error
    @app.get("/")
    @pydantic_api()
    def do_work() -> Union[dict, MyResponseModel]:
        ...
        return {
            "field1": "foo",
            "field2": 1234,
        }

    # Return something that isn't a dict or a model.
    # What you get here depends on how Flask supports what you are returning.
    # If it isn't a dict or a model, @pydantic_api will just pass it through.
    @app.get("/")
    @pydantic_api()
    def do_work() -> SomthingElse:
        ...
        return SomethingElse()
```


## Error Handling

By default, errors on pydantic validations of inputs will return a 400 HTTP status
code with a json response body that encodes the pydantic errors in its native format
(loc, msg, etc).
You can return a status code other than 400 by setting the flask config
`FLASK_PYDANTIC_API_ERROR_STATUS_CODE`.

If you want to handle the error differently (for example to customize the data structure
of the errors), you can turn off the automatic error handling by settings the
flask config `FLASK_PYDANTIC_API_RENDER_ERRORS` to `False`.

When error handling is turned off, pydantic validation errors will throw the
`pydantic.ValidationError` exception.  You will need to handle that exception
or else the server response will be a 500 server error. See [Flask Registering
Error Handlers](https://flask.palletsprojects.com/en/2.2.x/errorhandling/#registering).

**Response Validation Errors:**

If pydantic validation fails on your response object, the error will never be serialized
and returned in the response.  This is because the client user cannot easily distinguish
between the error happening on input or on your response.  Response validation errors will
throw an exception and yield a 500 server error.

<a name="serializer"></a>
## Using the Enhanced Serializer

This module supports [pydantic-enhanced-serializer](https://github.com/adamsussman/pydantic-enhanced-serializer).
It will use it automatically if installed.

The argument parameter used to select fields and expansions is
`fields`.  This can be customized with the `request_fields_name`
parameter of `@pydantic_api`.  You do not need to specify the `fields`
parameter in your function arguments or request body model.

The `fields` parameter may be in the query string or in the post body.  It can
be a list of strings or a string of field names separated by commas.

The maxium expansion depth defaults to 5 and can be controlled with
the `maximum_expansion_depth` parameter of `@pydantic_api`

Example:

```python
   from typing import ClassVar
   from pydantic import BaseModel
   from pydantic_enhanced_serializer import FielsetConfig

    class MyResponse(BaseModel):
        field1: str
        field2: str

        fieldset_config: ClassVar = FieldsetConfig(
            fieldsets = {
                default: ["field2"],
            }
        )

    @app.get("/something")
    @pydantic_api()
    def get_something() -> MyResponse:
        return MyResponse(field1="value1", field2="value2")
```

```console

    curl http://localhost:8080/something?fields=field1,field2
    curl http://localhost:8080/something?fields=field1&fields=field2

    curl -X POST \
        -H'Content-Type: application/json' \
        -d '{"fields": ["field1", "field2"]} \
        http://localhost:8080/something

```

See [Pydantic Enhanced Serializer](https://github.com/adamsussman/pydantic-enhanced-serializer)
for more information.


<a name="fileuploads"></a>
### File Uploads

File uploading with `multipart/form-data` content into pydantic request models is supported and
the usual required and type checks will be done.

Multiple files can be uploaded in the same request so long as each has a distinct field name.

```python

    from pydantic import BaseModel
    from pydantic_api import UploadedFile, pydantic_api

    class MyRequest(BaseModel):
        photo: UploadedFile
        caption: str

    @app.post("/upload-photo"
    @pyantic_api()
    def upload_photo(body: MyRequest) -> MyResponse:
        binary_file_data = body.photo.read()  # body.photo is werkzeug.datastructures.FileStorage object
        file_name = body.photo.filename

        ...
```

```console
    curl -F photo=@some_file.jpg -F caption="A great picture!" http://localhsot:8080/upload-photo
```


## License

This project is licensed under the terms of the MIT license.
