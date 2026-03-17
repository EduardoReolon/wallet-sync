"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, reverse_lazy
from django.views.generic import CreateView
from expenses.views import home, ler_nota, sincronizar_email
from accounts.forms import CustomUserCreationForm
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('contas/', include('django.contrib.auth.urls')),
    
    # Rota de registro (nova)
    path('contas/registrar/', CreateView.as_view(
        template_name='registration/register.html',
        form_class=CustomUserCreationForm,
        success_url=reverse_lazy('login')
    ), name='register'),

    path('', home, name='home'),
    path('ler-nota/', ler_nota, name='ler_nota'),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript')),
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json')),
    path('sincronizar-email/', sincronizar_email, name='sincronizar_email'),
]