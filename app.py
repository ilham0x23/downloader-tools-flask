from flask import Flask, request, send_file, jsonify, abort
from engine import *
import os
from functools import wraps
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import shutil
from secrets import token_urlsafe
import eventlet
from eventlet import wsgi
from flask_cors import CORS
import qrcode
from io import BytesIO

app = Flask(__name__,)
CORS(app)
app.secret_key = "myappv2x"
app.config['UPLOAD_FOLDER'] = 'media/youtube'
app.config['SESSION_TYPE'] = 'filesystem'
token_to_filename_mapping = {}
linksource = 'source_url'

@app.route('/')
def index():
    response_data = {
                "Status": 'Ready',
                "puh": 'Ampun'
            }
    return jsonify(response_data)

class erorr_handler:

    @app.route('/maintenance')
    def maintenance():
        response_data = {"Status": 'Server Under Maintenance'}
        return jsonify(response_data)

    @app.errorhandler(500)
    def internal_server_error(e):
        response_data = {
                    "error": {
                    "code": 500,
                    "message": "Internal Server Erorr"
                }
            }
        return jsonify(response_data)

    @app.errorhandler(404)
    def page_not_found_error(e):
        response_data = {
                    "error": {
                    "code": 404,
                    "message": "Page Not Found"
                }
            }
        return jsonify(response_data)

    @app.errorhandler(405)
    def method_not_allowed_error(e):
        response_data = {
                    "error": {
                    "code": 405,
                    "message": "Method not Allowed"
                }
            }
        return jsonify(response_data)

# AUTH KE API ENDPOINT
VALID_API_KEYS = ["theworldinyourhand", "Ilhmlnaa023"]

def get_api_keys_from_endpoint(api_endpoint):
    response = requests.get(api_endpoint)
    if response.status_code == 200:
        api_keys_json = response.json()
        return api_keys_json.get("keys", [])
    else:
        return []

def validate_api_key(api_key):
    try:
        api_keys_from_server = get_api_keys_from_endpoint("http://172.20.20.20:3080/key")
    except Exception as e:
        print(f"Failed to retrieve API keys from server: {e}")
        api_keys_from_server = []

    all_api_keys = set(VALID_API_KEYS + api_keys_from_server)
    return api_key in all_api_keys

def api_key_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("Api-Key")

        if not api_key or not validate_api_key(api_key):
            error_response = {
                "error": {
                    "code": 401,
                    "message": "Unauthorized: Invalid API key."
                }
            }
            return jsonify(error_response), 401

        return func(*args, **kwargs)

    return decorated_function

def download_instagram_file_by_token(random_token, extension):
        actual_filename = token_to_filename_mapping.get(random_token)

        if actual_filename is not None:
            media_folder = os.path.join("media", "instagram")
            file_path = os.path.join(media_folder, actual_filename)

            return send_file(file_path, as_attachment=True, download_name=f"{actual_filename.split('.')[0]}.{extension}")
        else:
            abort(404, description="File not found.")


#############ROUTE SECTION###################
@app.route('/qrcode')
def generate_qrcode():
    text = request.args.get('data', '')

    # Membuat QR code
    qr = qrcode.QRCode(
        version=4,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Menyimpan QR code ke dalam memory buffer
    img_bytes = BytesIO()
    img.save(img_bytes)
    img_bytes.seek(0)

    # Mengirimkan QR code sebagai file gambar
    return send_file(img_bytes, mimetype='image/png')

class sosial_downloader:
# Youtube Downloader Start
    @app.route('/youtube', methods=['GET', 'POST'])
    @api_key_required
    def youtube_downloader_page():
        new_file = None

        if request.method == 'POST':
            video_url = request.form[linksource]
            title = youtube_title(video_url)

            download_option = request.form.get('download_option')
            download_mp3 = download_option == "audio"
            download_mp4 = download_option == "video"

            if download_mp3:
                title += ".mp3"
                title, new_file = download_audio_yt(video_url, os.path.join(app.config['UPLOAD_FOLDER'], title))
            elif download_mp4:
                title += ".mp4"
                title, new_file = download_video_yt(video_url, os.path.join(app.config['UPLOAD_FOLDER'], title))

        if new_file is not None:
            # Generate a random token
            random_token = token_urlsafe(12)
            token_to_filename_mapping[random_token] = os.path.basename(new_file)
            url = f"/d/youtube/{random_token}"
        
            response_data = {
                "title" : os.path.basename(new_file),
                "status": 'success',
                "url": url
            }
        else:
            response_data = {
                "status": 'error',
                "error": "Failed to download the file."
            }

        return jsonify(response_data)

    @app.route('/d/youtube/<random_token>')
    def download_youtube_file_by_token(random_token):
        actual_filename = token_to_filename_mapping.get(random_token)

        if actual_filename is not None:
            media_folder = os.path.join("media/youtube")
            file_path = os.path.join(media_folder, actual_filename)
            return send_file(file_path, as_attachment=True)
        else:
            abort(404, description="File not found.")


    @app.route('/v2/youtube', methods=['GET'])
    def download_video():
        try:
            video_url = request.args.get('url')

            if not video_url:
                return jsonify(error='Invalid video URL'), 400

            yt = YouTube(video_url)
            
            video_title = yt.title
            video_thumbnail = [{'url': thumb['url'], 'width': thumb['width'], 'height': thumb['height']} for thumb in yt.vid_info['videoDetails']['thumbnail']['thumbnails']]
            
            cleaned_title = ''.join(c for c in video_title if c.isalnum() or c.isspace())
            cleaned_title = cleaned_title.replace(' ', '_')

            download_links = [{'quality': stream.resolution or 'Audio Only', 'type': stream.mime_type.split('/')[-1], 'url': stream.url} for stream in yt.streams]
            response_data = {'title': video_title, 'thumbnail': video_thumbnail, 'downloadLinks': download_links}

            return jsonify(response_data)

        except Exception as e:
            print(e)
# Youtube Downloader End

# Twitter Downloader Start
    @app.route('/twitter', methods=['POST', 'GET'])
    @api_key_required
    def twitter_downloader():
        if request.method == 'POST':
            url = request.form[linksource]
            option = request.form['download_option'] 

            headers = {
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": "twitter-downloader-download-twitter-videos-gifs-and-images.p.rapidapi.com"
            }

            query_params = {
                "url": url
            }

            try:
                response = requests.get(TWITTER_API_URL, headers=headers, params=query_params)
                data = response.json()

                description = data.get("description")

                if option == "image":
                    media = data.get("media", {})
                    photos = media.get("photo", [0])
                    photo_proses = [photo.get("url") for photo in photos]
                    photo_url = photo_proses[0] if photo_proses else None
                    # hasil_download = [{"name": description, "url": photo_url}]
                    response_data = {
                        "status": 'success',
                        "url": photo_url,
                        "title": description
                    }

                elif option == "video":
                    media = data.get("media", {})
                    video = media.get("video", {})
                    video_variants = video.get("videoVariants", [])
                    url = video_variants[0].get("url")  # Mengambil URL video pertama
                    response_data = {
                        "status": 'success',
                        "url": url,
                        "title": description
            }
                else:
                    url = None
                    response_data = {
                        "status": 'error',
                        "error": "Failed to download the file."
                    }

                
                return jsonify(response_data)
            
            except requests.exceptions.RequestException as e:
                return f"Error: {str(e)}"

 # Twitter Downloader End

# Instagram Downloader Start
    @app.route('/instagram', methods=['GET', 'POST'])
    @api_key_required
    def instagram_downloader():
        url = request.form[linksource]
        
        formatted_date, image_count, video_count = download_post_ig(url)  
        random_token = token_urlsafe(12)
        file_name_prefix = formatted_date
        
        # Loop through the image_count to generate URLs and tokens
        image_urls = {}
        for i in range(1, image_count + 1):
            random_token_image_i = f"{random_token}img{i}"
            file_name_image = f"{file_name_prefix}.jpg" if image_count == 1 else f"{file_name_prefix}_{i}.jpg"
            token_to_filename_mapping[random_token_image_i] = os.path.basename(file_name_image)
            url_image = f"/d/instagram/image/{random_token_image_i}"
            # image_urls.append(url_image)
            image_urls[f"img{i}"] = url_image

        video_urls = {}
        video_start_number = 2 if image_count > 1 else 1 
        for i in range(video_start_number, video_start_number + video_count):
            random_token_video_i = f"{random_token}vid{i}"
            file_name_video = f"{file_name_prefix}.mp4" if video_count == 1 else f"{file_name_prefix}_{i}.mp4"
            token_to_filename_mapping[random_token_video_i] = os.path.basename(file_name_video)
            url_video = f"/d/instagram/video/{random_token_video_i}"
            video_urls[f"vid{i}"] = url_video
        
        response_data = {
            "status": 'success',
            "url": {
                "image": image_urls,
                "video": video_urls
            }
        }
        
        return jsonify(response_data)

    @app.route('/d/instagram/image/<random_token>')
    def download_instagram_image_by_token(random_token):
        return download_instagram_file_by_token(random_token, 'jpg')

    @app.route('/d/instagram/video/<random_token>')
    def download_instagram_video_by_token(random_token):
        return download_instagram_file_by_token(random_token, 'mp4')


# Instagram Downloader End

# Tiktok Downloader Start
    @app.route('/tiktok', methods=['POST', 'GET'])
    @api_key_required
    def tiktok_downloader_page():
        if request.method == 'POST':
            url = request.form[linksource]
            option = request.form['download_option']  # This should be either "audio" or "video"
            headers = {
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": "tiktok-video-no-watermark2.p.rapidapi.com"
            }

            query_params = {
                "url": url
            }

            try:
                response = requests.get(TIKTOK_API_URL, headers=headers, params=query_params)
                data = response.json()

                if option == "audio":
                    audio_url = data.get("data", {}).get("music")
                    audio_title = data.get("data", {}).get("title")
                    url = audio_url
                    response_data = {
                        "status": "success",
                        "title": audio_title,
                        "url": url
                    }

                elif option == "video":
                    video_url = data.get("data", {}).get("play")
                    video_title = data.get("data", {}).get("title")
                    url = video_url
                    response_data = {
                        "status": "success",
                        "title": video_title,
                        "url": url
                    }
                    
                return jsonify(response_data)
            except requests.exceptions.RequestException as e:
                response_data = {
                    "status": "error",
                    "error": str(e)
                }
            

    # @app.route('/downloaded_tiktok/<file_name>')
    # def download_tiktok_file(file_name):
    #     media_folder = os.path.join("media", "tiktok")
    #     file_path = os.path.join(media_folder, file_name)
    #     return send_file(file_path, as_attachment=True)


# Tiktok Downloader End

# Spotify Downloader Start
    @app.route('/spotify', methods=['GET', 'POST'])
    @api_key_required
    def spotify_downloader():
        if request.method == 'POST':
            song_url = request.form[linksource]
            output_folder = os.path.join("media/spotify")

            try:
                title = download_song_from_spotify(song_url, output_folder)
                file_name = f"{title}.mp3"

                # Generate a random token
                random_token = token_urlsafe(12)

                # Store the mapping of the token to the actual filename
                token_to_filename_mapping[random_token] = file_name

                # Create the URL with the random token
                url = f"/d/spotify/{random_token}"

                response_data = {
                    "status": 'success',
                    "title": file_name,
                    "url": url
                }
            except Exception as e:
                response_data = {
                       "status": "error",
                       "error": str(e)
                    }

            return jsonify(response_data)

    @app.route('/d/spotify/<random_token>')
    def download_spotify_file_by_token(random_token):
        # Get the actual filename from the mapping
        actual_filename = token_to_filename_mapping.get(random_token)

        if actual_filename is not None:
            media_folder = os.path.join("media", "spotify")
            file_path = os.path.join(media_folder, actual_filename)
            return send_file(file_path, as_attachment=True)
        else:
            abort(404, description="File not found.")

# Spotify Downloader End

# Fungsi untuk menghapus folder
def delete_folders_contents():
    media_folder = os.path.join("media")

    if os.path.exists(media_folder):
        try:
            shutil.rmtree(media_folder) 
            print("Downloader Media Folder Clear")
        except Exception as e:
            print(f"Error deleting media folder: {e}")

# Schedule the deletion job to run every 1 minute
scheduler = BackgroundScheduler()
scheduler.add_job(delete_folders_contents, 'interval', hours=1)
scheduler.start()


# ...

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5080, debug=True)
    # wsgi.server(eventlet.listen(('0.0.0.0', 5080)), app)
    # wsgi.server(eventlet.listen(("0.0.0.0", 3000)), app, debug=True)

# ...
