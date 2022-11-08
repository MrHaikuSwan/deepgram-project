import os
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import mutagen

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///files.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = '/mnt/c/Users/Ashwin/Documents/Programming/deepgram-interview/audio_files'
db = SQLAlchemy(app)


class Files(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100))
    duration = db.Column(db.Float)
    bitrate = db.Column(db.Integer)
    channels = db.Column(db.Integer)
    sample_rate = db.Column(db.Integer)

    def as_dict(self):
        return {
            'filename': self.filename,
            'duration': self.duration,
            'bitrate': self.bitrate,
            'channels': self.channels,
            'sample_rate': self.sample_rate
        }

class FileManager:
    uid = 0

    @classmethod
    def get_filename(cls, advance=True):
        filename = f"file{cls.uid}.wav"
        if advance:
            cls.uid += 1
        return cls.add_filename(filename)
    
    @classmethod
    def add_filename(cls, filename):
        name, ext = filename.rsplit('.', 1)
        num = 1
        while Files.query.filter_by(filename=filename).first():
            filename = f"{name}-{num}.{ext}"
            num += 1
        return filename


@app.route('/')
def home():
    return "<h1>Browser UI</h1>"


@app.route('/post', methods=['POST'])
def receive_audio():
    filename = download_file()
    if filename is False:
        return "Invalid request", 400
    
    # Validate audio file using mutagen
    fp = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    audio = mutagen.File(fp)

    # Remove file if saved data is not a valid audio file
    if audio is None:
        os.remove(fp)
        return "Bad audio file\n", 400
    
    # Add validated file with metadata to database
    metadata = {
        'filename': filename,
        'duration': getattr(audio.info, 'length', None),
        'bitrate': getattr(audio.info, 'bitrate', None),
        'channels': getattr(audio.info, 'channels', None),
        'sample_rate': getattr(audio.info, 'sample_rate', None)
    }
    info = Files(**metadata)
    db.session.add(info)
    db.session.commit()
    return {"filename": filename}


@app.route('/download')
def serve_audio():
    name, audio_file = fetch_single_query_record()
    if not name:
        return "Request must include name query parameter", 400
    elif not audio_file:
        return "File not found", 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], name)


@app.route('/list')
def serve_filenames():
    args = request.args
    maxduration = args.get('maxduration', float('inf'))
    minduration = args.get('minduration', float('-inf'))
    verbose = (args.get('verbose', False) == 'true')
    files = Files.query.filter(Files.duration >= minduration, Files.duration <= maxduration).all()
    if verbose:
        response = {'files': [f.as_dict() for f in files]}
    else:
        response = {'files': [f.filename for f in files]}
    return response
    

@app.route('/info')
def serve_metadata():
    name, audio_file = fetch_single_query_record()
    if not name:
        return "Request must include name query parameter", 400
    elif not audio_file:
        return "File not found", 404
    return audio_file.as_dict()


def download_file():
    '''Handles downloading POSTed file, returns filename if successful, False if unsuccessful'''
    contentType = request.headers.get('Content-Type')
    # curl --data-binary option used
    if contentType.startswith("application/x-www-form-urlencoded"):
        filename = FileManager.get_filename()
        with open(filename, 'wb') as f:
            f.write(request.stream.read())
        return filename
    # curl -F option used
    elif contentType.startswith("multipart/form-data"):
        file = request.files.get('file')
        filename = FileManager.add_filename(secure_filename(file.filename))
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    # Invalid request
    else:
        return False

def fetch_single_query_record():
    '''Handles fetching single record from database with name query parameter,
    returns (name, query response)'''
    args = request.args
    name = args['name'] if 'name' in args else None
    audio_file = Files.query.filter_by(filename=name).first() if name else None
    return name, audio_file
