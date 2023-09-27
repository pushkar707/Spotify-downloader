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
import shutil
import datetime


load_dotenv()
# daemon_process_started = False

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

def get_video_link(name,artist,request):
    try:
        op = webdriver.ChromeOptions()
        op.add_argument('headless')
        driver = webdriver.Chrome(options=op)
        url = f"https://www.youtube.com/results?search_query={name} {artist}"
        # driver.minimize_window()
        driver.get(url)
        time.sleep(2)
        content = driver.page_source.encode('utf-8').strip()
        soup = BeautifulSoup(content,"html.parser")
        firstVid = soup.select_one('ytd-video-renderer a.yt-simple-endpoint.inline-block.style-scope.ytd-thumbnail')
        driver.quit()
        return firstVid.get('href')
    except Exception:
        request.session['tracks'] = request.session.get("tracks")+[{'name':name,'artist':artist}]
        print("Failed to fetch link")

def download_video(item,playlist_name,request):
    # Getting song's link
    try:
        name = item['name']
        image = item['image']
        artist = item['artist']
        # name = item['track']['name']
        # image = item['track']['album']['images'][0]['url']
        # artist = item['track']['album']['artists'][0]['name']
        link = get_video_link(name,artist,request)

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
       request.session['daemon_process_started'] = False
       return e


def download_songs_long(playlist_name,tracks,request):
    threads = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        # for i in (json_result['items']):
        for i in tracks:
            threads.append(executor.submit(download_video, i,playlist_name,request))
    timer = threading.Timer(10000, del_data,args=(request,))
    timer.start()

# Create your views here.

# rearranged templates
def home(request):
    if(request.session.items()):
        return redirect("/reset")
    if(request.method == "GET"):
        print(request.session.items())
        return render(request,"homee.html",{"test":'test'})
    else:
        try:
            link = request.POST.get("link")
            playlist_id = link.split("?")[0].split("/")[-1]

            # Getting playlist from spotify API
            token = get_token()
            playlist = requests.get(f"https://api.spotify.com/v1/playlists/{playlist_id}", headers={
                "Authorization": "Bearer " + token
            })

            playlist_name = json.loads(playlist.content)['name']
            tracks = requests.get(f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", headers={
                "Authorization": "Bearer " + token
            })
            json_result = json.loads(tracks.content)
        except KeyError:
            return HttpResponse("Could not find your playlist. Maybe it is private. Go back <a href='/'>Home</a>")
        tracks = []
        for item in json_result['items']:
            name = item['track']['name']
            image = item['track']['album']['images'][2]['url']
            artist = item['track']['album']['artists'][0]['name']
            tracks.append({'name':name,'artist':artist,'image':image})
        request.session['playlist_original'] = playlist_name
        request.session['playlist'] = playlist_name.replace(" ",'-')+playlist_id
        request.session['tracks'] = tracks
        return render(request,'search_results.html',{'playlist_name':playlist_name,'tracks':tracks})
    
def zip_route(request):
    tracks = request.session.get("tracks")
    playlist = request.session.get("playlist")
    playlist_original = request.session.get("playlist_original")
    if (not tracks):
        return redirect("/")
    daemon_process_started = request.session.get("daemon_process_started")

    if not daemon_process_started:
        request.session['daemon_process_started'] = True
        t = threading.Thread(target=download_songs_long,args=(playlist,tracks,request))
        t.setDaemon(True)
        t.start()
    return render(request, 'processing.html', {"total_songs":len(tracks),'playlist':playlist_original})

def check_songs_dowloaded(request):
    playlist = request.session.get("playlist")
    tracks = request.session.get("tracks")
    if (not playlist):
        return redirect("/")
    try:
        file_list = os.listdir(os.path.join(settings.MEDIA_ROOT, playlist))
        mp3_files = [file_name for file_name in file_list if file_name.endswith('.mp3')]
        # mp3_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        len_mp3 = len(mp3_files)
        progress = (len_mp3/len(tracks))*100        
    except FileNotFoundError as E:
        print(E)
        progress = 0
        len_mp3 = 0
        mp3_files = [""]

    return JsonResponse({'progress':progress,"completed":len_mp3,"last_song":tracks[len_mp3-1]['name']})

def check_mp3_files(request):
    try:
        playlist = request.session.get("playlist")
        file_list = os.listdir(os.path.join(settings.MEDIA_ROOT, playlist))
        mp3_files = [file_name for file_name in file_list if file_name.endswith('.mp3')]
        len_mp3 = len(mp3_files)
    except FileNotFoundError:
        return JsonResponse({"completed":False})
    if not request.session.get('mp3'):
        request.session["mp3"] = len_mp3
        return JsonResponse({"completed":False})
    else:
        previous = request.session.get('mp3')
        if(previous == len_mp3):
            return JsonResponse({"completed":True})
        else:
            request.session["mp3"] = len_mp3
            return JsonResponse({"completed":False})

def del_data(request):
    playlist = request.session.get("playlist")
    folder_path = os.path.join(settings.MEDIA_ROOT,playlist)
    request.session.flush()
    if os.path.exists(folder_path): 
        shutil.rmtree(folder_path)
        try:
            os.remove(folder_path+".zip")
        except Exception:
            pass

def completed(request):
    playlist_original = request.session.get('playlist_original')
    playlist = request.session.get('playlist')
    print(playlist)
    if not playlist:
        return redirect("/")
    request.session['daemon_process_started'] = False
    timer = threading.Timer(10000, del_data,args=(request,))
    timer.start()
    return render(request,'download_zip.html',{'playlist':playlist,'playlist_original':playlist_original})
    # return HttpResponse(f"Zip file is ready <br> <a href='/download-folder/{playlist}/'>Download Folder as Zip</a>")

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


def reset(request):
    del_data(request)
    return redirect("/")
