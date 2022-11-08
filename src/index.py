import os
from flask import Flask, render_template, request, redirect, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import mutagen


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///files.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = '/mnt/c/Users/Ashwin/Documents/Programming/deepgram-interview/audio_files'
db = SQLAlchemy(app)


class File(db.Model):
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
    def generate_filename(cls, advance=True):
        filename = f"file{cls.uid}.wav"
        if advance:
            cls.uid += 1
        return cls.add_filename(filename)
    
    @classmethod
    def add_filename(cls, filename):
        name, ext = filename.rsplit('.', 1)
        num = 1
        while File.query.filter_by(filename=filename).first():
            filename = f"{name}-{num}.{ext}"
            num += 1
        return filename


@app.route('/')
def home():
    audio_files = db.session.query(File).all()
    audio_files = [f.as_dict() for f in audio_files]
    audio_files.sort(key=lambda x: x['filename'].lower())
    return render_template("base.html", files=audio_files)


@app.route('/post', methods=['POST'])
def receive_audio():
    app.logger.info(request.headers)
    filename = download_file()
    if filename is False:
        return "Invalid request", 400
    isValid = parse_and_validate_file(filename)
    if isValid:
        return redirect('/')
    else:
        return "Bad audio file\n", 400


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
    maxbitrate = args.get('maxbitrate', float('inf'))
    minbitrate = args.get('minbitrate', float('-inf'))
    channels = args.get('channels')
    sample_rate = args.get('sample_rate')
    verbose = (args.get('verbose', False) == 'true')
    query = File.query.filter(
        File.duration >= minduration, File.duration <= maxduration,
        File.bitrate >= minbitrate, File.bitrate <= maxbitrate)
    if channels:
        query = query.filter_by(channels=channels)
    if sample_rate:
        query = query.filter_by(sample_rate=sample_rate)
    files = query.all()
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


## THIS IS ONLY HERE FOR DEMO / DEV PURPOSES -- NOT PART OF PRODUCTION
@app.route('/clear')
def clear_database():
    db.session.query(File).delete()
    db.session.commit()
    for name in os.listdir(app.config['UPLOAD_FOLDER']):
        fp = os.path.join(app.config['UPLOAD_FOLDER'], name)
        os.remove(fp)
    return redirect('/')
## THIS IS ONLY HERE FOR DEMO / DEV PURPOSES -- NOT PART OF PRODUCTION


def download_file():
    '''
    Handle downloading POSTed file.
    
    Returns filename if successful
    Returns False if unsuccessful'''
    contentType = request.headers.get('Content-Type')
    # curl --data-binary option used
    if contentType.startswith("application/x-www-form-urlencoded"):
        filename = FileManager.generate_filename()
        fp = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(fp, 'wb') as f:
            f.write(request.stream.read())
        return filename
    # curl -F option used
    elif contentType.startswith("multipart/form-data"):
        file = request.files.get('file')
        filename = FileManager.add_filename(secure_filename(file.filename))
        if not filename:
            filename = FileManager.generate_filename()
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    # Invalid request
    else:
        return False


def parse_and_validate_file(filename):
    '''
    Handle parsing and validating the input audio file with Mutagen.

    Returns True and logs in database if file is valid
    Returns False and deletes from memory if file is invalid
    '''
    # Validate audio file using mutagen
    fp = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    audio = mutagen.File(fp)

    # Remove file if saved data is not a valid audio file
    if audio is None:
        os.remove(fp)
        return False
    
    # Add validated file with metadata to database
    metadata = {
        'filename': filename,
        'duration': getattr(audio.info, 'length', None),
        'bitrate': getattr(audio.info, 'bitrate', None),
        'channels': getattr(audio.info, 'channels', None),
        'sample_rate': getattr(audio.info, 'sample_rate', None)
    }
    info = File(**metadata)
    db.session.add(info)
    db.session.commit()
    return True


def fetch_single_query_record():
    '''
    Handle fetching single record from database with name query parameter.
    
    Returns (name, query response) -- if name is not provided or file does not
    exist in database, the corresponding element is set to None
    '''
    args = request.args
    name = args['name'] if 'name' in args else None
    audio_file = File.query.filter_by(filename=name).first() if name else None
    return name, audio_file
