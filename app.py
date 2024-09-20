from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import get_db, close_db_connection, init_db
from spotipy.oauth2 import SpotifyOAuth
import spotipy
import sqlite3
import random
import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key'

SPOTIPY_CLIENT_ID = 'c73360dad6ec44c28ba47e3269aea3dd'
SPOTIPY_CLIENT_SECRET = '29470a9bb1374f44856f7ccdc98f05e0'
SPOTIPY_REDIRECT_URI = 'http://localhost:5000/callback'

sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                        client_secret=SPOTIPY_CLIENT_SECRET,
                        redirect_uri=SPOTIPY_REDIRECT_URI,
                        scope='user-library-read user-read-playback-state user-modify-playback-state')

@app.template_filter('format_date')
def format_date(value):
    if isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%d')
    return value

def get_spotify():
    token_info = sp_oauth.get_access_token(as_dict=False)
    if token_info:
        return spotipy.Spotify(auth=token_info)
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    return render_template('index.html', users=users)

@app.teardown_appcontext
def teardown_db(exception):
    close_db_connection(exception)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM Users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user and password == user['password']:
            session['logged_in'] = True
            session['user_id'] = user['user_id']
            flash('Login successful.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')

@app.route('/view_playlist/<int:playlist_id>')
@login_required
def view_playlist(playlist_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT s.*
        FROM Songs s
        JOIN PlaylistSongs ps ON s.song_id = ps.song_id
        WHERE ps.playlist_id = ? AND s.user_id = ?
    """, (playlist_id, session['user_id']))
    
    songs = cursor.fetchall()
    return render_template('view_playlist.html', songs=songs, playlist_id=playlist_id)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/add_songs_to_playlist', methods=['GET', 'POST'])
@login_required
def add_songs_to_playlist():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        song_id = request.form['song_id']
        playlist_id = request.form['playlist_id']

        cursor.execute('INSERT INTO PlaylistSongs (playlist_id, song_id) VALUES (?, ?)', (playlist_id, song_id))
        db.commit()
        flash('Song added to playlist!', 'success')
        return redirect(url_for('show_playlists'))

    user_id = session['user_id']
    cursor.execute('SELECT * FROM Songs WHERE user_id = ?', (user_id,))
    songs = cursor.fetchall()

    cursor.execute('SELECT * FROM Playlists WHERE user_id = ?', (user_id,))
    playlists = cursor.fetchall()

    return render_template('add_songs.html', songs=songs, playlists=playlists)

@app.route('/user_songs')
@login_required
def user_songs():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM Songs WHERE user_id = ?", (user_id,))
    songs = cursor.fetchall()

    cursor.execute("SELECT * FROM Playlists WHERE user_id = ?", (user_id,))
    playlists = cursor.fetchall()

    return render_template('user_songs.html', songs=songs, playlists=playlists)

@app.route('/delete_song_from_playlist/<int:song_id>/<int:playlist_id>', methods=['POST'])
@login_required
def delete_song_from_playlist(song_id, playlist_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM PlaylistSongs WHERE song_id = ? AND playlist_id = ?", (song_id, playlist_id))
    db.commit()

    flash('Song removed from playlist successfully!', 'success')
    return redirect(url_for('view_playlist', playlist_id=playlist_id))

@app.route('/search', methods=['GET', 'POST'])
def search_song():
    sp = get_spotify()  
    if not sp:
        flash('Spotify client not initialized.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        query = request.form['query']
        results = sp.search(q=query, type='track', limit=5)
        tracks = results['tracks']['items']

        db = get_db()
        cursor = db.cursor()

        song_results = []
        for track in tracks:
            track_name = track['name']
            artist_name = track['artists'][0]['name']
            duration = track['duration_ms']
            release_year = track['album']['release_date'][:4]

            artist_info = sp.artist(track['artists'][0]['id'])
            artist_genre = ', '.join(artist_info['genres']) if artist_info['genres'] else 'Unknown'

            cursor.execute('SELECT artist_id FROM Artists WHERE artist_name = ?', (artist_name,))
            artist_row = cursor.fetchone()

            if artist_row:
                artist_id = artist_row[0]
            else:
                cursor.execute('INSERT INTO Artists (artist_name, genre) VALUES (?, ?)', 
                               (artist_name, artist_genre))
                db.commit()
                artist_id = cursor.lastrowid

            song_results.append({
                'track_name': track_name,
                'artist_name': artist_name,
                'artist_id': artist_id,
                'duration': duration,
                'release_year': release_year
            })

        return render_template('search_results.html', songs=song_results)

    return render_template('search.html')

@app.route('/save_song', methods=['POST'])
@login_required
def save_song():
    if request.method == 'POST':
        track_name = request.form['track_name']
        artist_name = request.form['artist_name']
        artist_id = request.form['artist_id']
        genre = request.form['genre']
        duration = request.form['duration']
        release_year = request.form['release_year']
        user_id = session['user_id']

        db = get_db()
        cursor = db.cursor()

        cursor.execute('INSERT INTO Songs (song_title, artist_name, artist_id, genre, duration, release_year, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (track_name, artist_name, artist_id, genre, duration, release_year, user_id))
        db.commit()

        flash('Song saved successfully!', 'success')
        return redirect(url_for('show_playlists'))

@app.route('/callback')
def callback():
    token_info = sp_oauth.get_access_token(request.args.get('code'))
    session['token_info'] = token_info

    flash('Login successful! You can now search for songs.', 'success')
    return redirect(url_for('search_song'))

@app.route('/spotify_login')
def spotify_login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']

        user_id = random.randint(0, 100000)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE username = ? OR email = ?", (username, email))
        existing_user = cursor.fetchone()

        conn.close()

        if not username or not fullname or not email or not password:
            return render_template('signup.html', error_message="All fields are required.")
        if "@" not in email:
            return render_template('signup.html', error_message="Invalid email address.")
        if existing_user:
            return render_template('signup.html', error_message="Username or email already taken.")

        registration_date = datetime.datetime.now()

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Users (user_id, username, full_name, email, password, registration_date) VALUES (?, ?, ?, ?, ?, ?)",
                        (user_id, username, fullname, email, password, registration_date))
        conn.commit()
        conn.close()

        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/my_account')
@login_required
def my_account():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        columns = [description[0] for description in cursor.description]
        user = dict(zip(columns, row))
        return render_template('my_account.html', user=user)
    else:
        flash('User not found.', 'error')
        return redirect(url_for('index'))

@app.route('/playlist', methods=['GET', 'POST'])
@login_required
def create_playlist():
    if request.method == 'POST':
        playlist_name = request.form['playlist_name']
        user_id = session['user_id']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO Playlists (playlist_name, user_id) VALUES (?, ?)", (playlist_name, user_id))
        db.commit()

        flash('Playlist created successfully!', 'success')
        return redirect(url_for('show_playlists'))

    return render_template('playlists.html')

@app.route('/delete_playlist/<int:playlist_id>', methods=['POST'])
@login_required
def delete_playlist(playlist_id):
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM Playlists WHERE playlist_id = ? AND user_id = ?", (playlist_id, user_id))
    db.commit()

    flash('Playlist deleted successfully!', 'success')
    return redirect(url_for('show_playlists'))

@app.route('/playlists')
@login_required
def show_playlists():
    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM Playlists WHERE user_id = ?", (user_id,))
    playlists = cursor.fetchall()

    return render_template('playlists.html', playlists=playlists)

if __name__ == '__main__':
    app.run(debug=True)
