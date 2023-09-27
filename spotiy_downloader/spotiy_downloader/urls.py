"""
URL configuration for spotiy_downloader project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
from django.urls import path
from core.views import home,completed,download_folder_as_zip,zip_route,check_songs_dowloaded,reset,check_mp3_files

urlpatterns = [
    path('', home),
    path('processing/', zip_route),
    path('completed/', completed),
    path('download-folder/<str:folder_name>/', download_folder_as_zip),
    path('check-songs-downloaded/', check_songs_dowloaded),
    path('reset/', reset),
    path('check-mp3-files/', check_mp3_files),
    # path('redirect', redirect),
    path('admin/', admin.site.urls),
]
