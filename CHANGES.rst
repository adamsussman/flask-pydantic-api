Version 0.9.6
-------------

Released 2023-06-21

- Use a longer lived event_loop to run the render/expansion phase and make sure that the
  event loop is still open when the expander gathers its futures.

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
