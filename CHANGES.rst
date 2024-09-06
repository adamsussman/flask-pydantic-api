Version 1.3.1
-------------

Released 2024-09-06

- Fix https://github.com/adamsussman/flask-pydantic-api/issues/2: Correct Content-Type header when not using
  pydantic_enhanced_serializer

Version 1.3.0
-------------

Released 2024-09-06

- Add @pydantic_api parameter `get_request_model_from_query_string`.  This instructs the OpenAPI schema generator
  to put the request model's parameters into the query string specification.


Version 1.2.0
-------------

Released 2024-06-09

- Add pydantic_api parameter `success_status_code_by_response_model`.  This allows methods that specify a return
  type that is a Union of multiple BaseModels to also specify a specific http status code depending on which
  model is in the actual response.
- OpenAPI schemas will now correctly reflect cases where the response is a Union of multiple pydantic models including
  custom statuses per model.
- Allow method request body type to be a Union of a model with a file upload and another non-upload model


Version 1.1.0
-------------

Released 2023-12-01

- Removed openapi-pydantic as a methodology and moved to pure native python data structures
  (dicts, etc) for OpenAPI.
- Many reworks and fixes to how openapi schema is generated.


Version 1.0.0
-------------

Released 2023-11-27

BREAKING CHANGES

- Conversion to Pydantic 2.0.  Pydantic < 2.5 no longer supported.
- Added `model_dump_kwargs` argument to `@pydantic_api`


Version 0.10.0
--------------

Released 2023-10-12

- Added ability to get at the `fields` request value by adding a field: List[str] argument
  to the @pydantic_api wrapped work function.


Version 0.9.7 - recalled
Version 0.9.6 - recalled

Version 0.9.5
-------------

Released 2023-05-30

- Improve scope of catching pydantic validation errors when creating response models inside wrapper
  handlers and unintentionally showing those errors to API callers.


Version 0.9.4
-------------

Released 2023-05-17

- Add support for extra openapi schema data in @pydantic_api argument


Version 0.9.3
-------------

Released 2023-04-13

- Add support for file uploads via multipart/form-data in models and openapi schema

- Add `fields` parameter to openapi query strings and request bodies if response models
  have fieldsets defined.


Version 0.9.2
-------------

Released 2023-04-01

- Pass any kwargs for `get_openapi_schema` into `OpenAPI.parse_obj`.


Version 0.9.1
-------------

Released 2023-03-28

- Fix broken OpenAPI schemas for empty responses.


Version 0.9.0
-------------

Released 2023-03-18

- Initial public release.
