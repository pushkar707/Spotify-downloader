from django.shortcuts import HttpResponse,redirect
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


load_dotenv()


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
        time.sleep(10)
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
            'outtmpl': str(Path.home() / "Downloads" / playlist_name / name),
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
    playlist = requests.get("https://api.spotify.com/v1/playlists/2axSMVEIguykFjXHzRRHsZ", headers={
        "Authorization": "Bearer " + token
    })
    playlist_name = json.loads(playlist.content)['name']
    tracks = requests.get("https://api.spotify.com/v1/playlists/2axSMVEIguykFjXHzRRHsZ/tracks", headers={
        "Authorization": "Bearer " + token
    })
    json_result = json.loads(tracks.content)

    # threding:
    threads = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        for i in (json_result['items']):
            threads.append(executor.submit(download_video, i,playlist_name))
        # download_video(i,playlist_name)
        for task in as_completed(threads):
            print(task.result())

# Create your views here.
def home(request):
    t = threading.Thread(target=download_songs_long)
    t.setDaemon(True)
    t.start()
    return HttpResponse("Pending")

def completed(request):
    return HttpResponse("Playlist downloaded")
    