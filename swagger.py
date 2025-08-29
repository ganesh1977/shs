from drf_yasg import openapi

schema_info = openapi.Info(
    title="My API",
    default_version="v1",
    description="API documentation",
    contact=openapi.Contact(email="support@example.com"),
    license=openapi.License(name="BSD License"),
)
