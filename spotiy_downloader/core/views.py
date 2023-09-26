from django.shortcuts import HttpResponse,redirect,render
from django.http import JsonResponse
from dotenv import load_dotenv
import os
import requests
import base64
import json
from apiclient.discovery import build
import yt_dlp
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from django.conf import settings
import zipfile


load_dotenv()

download_completed = threading.Event()
daemon_process_started = False

def get_token():
    client_id = os.getenv('SPOTIPY_CLIENT_ID')
    secret_id = os.getenv('SPOTIPY_CLIENT_SECRET')
    # auth_string = client_id + ":" + secret_id
    auth_bytes = base64.b64encode((client_id + ":" + secret_id).encode("utf-8"))
    auth_base64 = auth_bytes.decode("utf-8")
    url = 'https://accounts.spotify.com/api/token/'
    headers = {
        "Authorization": "Basic " + auth_base64,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type":"client_credentials"}
    result = requests.post(url,headers=headers, data=data)
    json_result = json.loads(result.content)
    token = json_result['access_token']
    return token

def get_video_link(name,artist):
    try:
        op = webdriver.ChromeOptions()
        op.add_argument('headless')
        driver = webdriver.Chrome(options=op)
        url = f"https://www.youtube.com/results?search_query={name} {artist}"
        # driver.minimize_window()
        driver.get(url)
        time.sleep(5.5)
        content = driver.page_source.encode('utf-8').strip()
        soup = BeautifulSoup(content,"html.parser")
        firstVid = soup.select_one('ytd-video-renderer a.yt-simple-endpoint.inline-block.style-scope.ytd-thumbnail')
        driver.quit()
        return firstVid.get('href')
    except Exception:
        print("Failed to fetch link")

def download_video(item,playlist_name):
    # Getting song's link
    try:
        name = item['track']['name']
        image = item['track']['album']['images'][0]['url']
        artist = item['track']['album']['artists'][0]['name']
        link = get_video_link(name,artist)

        # Downloading song
        ydl_opts = {
            'format': 'bestaudio/best',
            "outtmpl": os.path.join(settings.MEDIA_ROOT, playlist_name, name),
            # 'outtmpl': str(Path.home() / "Downloads" / playlist_name / name),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        if link:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download("https://www.youtube.com" + link)
    except requests.exceptions.RequestException as e:
       print(e)


def download_songs_long():
    token = get_token()
    playlist = requests.get("https://api.spotify.com/v1/playlists/5BVYvnNOkwQCuyZoSZOO1e", headers={
        "Authorization": "Bearer " + token
    })
    playlist_name = json.loads(playlist.content)['name'].replace(" ","-")
    tracks = requests.get("https://api.spotify.com/v1/playlists/5BVYvnNOkwQCuyZoSZOO1e/tracks", headers={
        "Authorization": "Bearer " + token
    })
    json_result = json.loads(tracks.content)

    # threding:
    threads = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        for i in (json_result['items']):
            threads.append(executor.submit(download_video, i,playlist_name))
        # download_video(i,playlist_name)
        for task in as_completed(threads):
            print(task.result())
    download_completed.set()

def download_brrowser(file_path):
    pass
    # with open(file_path, 'rb') as mp3_file:
    #     response = HttpResponse(mp3_file.read(), content_type='audio/mpeg')
    #     response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
    #     return response

# Create your views here.
def home(request):
    global daemon_process_started

    if not daemon_process_started:
        daemon_process_started = True
        t = threading.Thread(target=download_songs_long)
        t.setDaemon(True)
        t.start()
    return render(request, 'home.html', {'download_completed': download_completed.is_set()})
    # return HttpResponse("Pending")

def completed(request):
    global daemon_process_started
    download_completed.clear()
    daemon_process_started = False
    return HttpResponse("Zip file is ready <br> <a href='/download-folder/app-testing/'>Download Folder as Zip</a>")

def download_folder_as_zip(request, folder_name):
    folder_path = os.path.join(settings.MEDIA_ROOT, folder_name)

    if os.path.exists(folder_path):
        # Create a zip file
        zip_file_path = os.path.join(settings.MEDIA_ROOT, f'{folder_name}.zip')
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, folder_path)
                    zipf.write(file_path, rel_path)

        # Serve the zip file as a response
        with open(zip_file_path, 'rb') as zip_file:
            response = HttpResponse(zip_file.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename={folder_name}.zip'
            return response
    else:
        # Handle the case where the folder doesn't exist
        return HttpResponse("Folder not found", status=404)
    
def check_download_status(request):
    return JsonResponse({'completed': download_completed.is_set(),"rfdvv":'fxvc'})