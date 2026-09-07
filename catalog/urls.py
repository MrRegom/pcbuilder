from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscador/", views.search, name="search"),
    path("armador/", views.builder, name="builder"),
    path("api/productos/", views.api_products, name="api_products"),
    path("api/armador/opciones/", views.api_builder_options, name="api_builder_options"),
    path("api/armador/resumen/", views.api_builder_summary, name="api_builder_summary"),
    path("api/armador/recomendar/", views.api_recommend, name="api_recommend"),
    path("api/armador/interpretar/", views.api_recommend_text, name="api_recommend_text"),
]
