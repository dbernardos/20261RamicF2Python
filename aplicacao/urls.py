from django.urls import path
from . import views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('', views.index, name="urlindex"),
    path('entrar', views.entrar, name="urlentrar"),
    path('sair', views.sair, name="urlsair"),
    path('cadastrarUsuario', views.cadastrarUsuario, name="urlcadastrarUsuario"),
    path('geraraficos', views.geragraficos, name="urlgeragraficos"),
    path('grafico', views.grafico, name="urlgrafico"),
    
    path('historico/', views.historico, name='urlhistorico'),
    path('coleta/', views.coleta2, name='urlcoleta'),

]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)