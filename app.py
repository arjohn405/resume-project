import os
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import spacy
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///resumes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Allowed file extensions for resume uploads
ALLOWED_EXTENSIONS = {'txt', 'pdf'}

# Ensure the upload folder exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database setup
db = SQLAlchemy(app)

# Dummy user storage in a text file (for demonstration)
USERS_FILE = 'users.txt'

# SpaCy setup
nlp = spacy.load('en_core_web_sm')

# User model (using SQLAlchemy)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    resume = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"User('{self.name}', '{self.email}')"

# Utility function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# Route for login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Dummy authentication (replace with actual authentication logic)
        if check_user_credentials(email, password):
            return redirect(url_for('upload'))
        else:
            return render_template('login.html', error='Invalid credentials. Please try again.')

    return render_template('login.html')

# Route for signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Dummy registration (replace with actual registration logic)
        if not user_exists(email):
            save_user_data(name, email, password)
            return redirect(url_for('upload'))
        else:
            return render_template('signup.html', error='Email already exists. Please use a different email.')

    return render_template('signup.html')

# Upload route (redirects here after login/signup)
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        
        if 'resume' not in request.files:
            return jsonify({'error': 'No file part'})
        
        resume_file = request.files['resume']
        
        if resume_file.filename == '':
            return jsonify({'error': 'No selected file'})
        
        if resume_file and allowed_file(resume_file.filename):
            filename = secure_filename(resume_file.filename)
            resume_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            resume_file.save(resume_path)
            
            # Read text content from the uploaded file
            if filename.endswith('.pdf'):
                try:
                    resume_content = extract_text(resume_path)
                except Exception as e:
                    return jsonify({'error': f'Error reading PDF file: {str(e)}'})
            else:
                try:
                    with open(resume_path, 'r', encoding='utf-8') as file:
                        resume_content = file.read()
                except Exception as e:
                    return jsonify({'error': f'Error reading text file: {str(e)}'})
            
            # Check if the user already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                # Update existing user's resume
                existing_user.name = name
                existing_user.resume = resume_content
            else:
                # Create a new user
                new_user = User(name=name, email=email, resume=resume_content)
                db.session.add(new_user)
            
            # Commit the transaction
            db.session.commit()
            
            # Analyze the resume content
            doc = nlp(resume_content)
            skills = extract_skills(doc)
            jobs_with_percentage, job_keywords = recommend_jobs_with_percentage(skills)
            
            # Highlight the keywords in the resume content
            highlighted_resume_content = highlight_resume_content(resume_content, job_keywords)
            
            return render_template('upload.html', resume_content=highlighted_resume_content, jobs=jobs_with_percentage)
        
        return jsonify({'error': 'File type not allowed'})

    return render_template('upload.html')


# Function to extract skills from resume (example implementation)
def extract_skills_and_highlight(doc):
    skills = []
    job_titles = []  # Example job titles
    company_names = []  # Example company names

    highlighted_content = []

    for token in doc:
        token_text = token.text
        token_lower = token_text.lower()

        if token_text in job_titles:
            highlighted_content.append(f'<span class="highlight-job-title">{token_text}</span>')
        elif token_text in company_names:
            highlighted_content.append(f'<span class="highlight-company">{token_text}</span>')
        elif token.pos_ in ['NOUN', 'PROPN']:
            skills.append(token_text)
            highlighted_content.append(f'<span class="highlight-skill">{token_text}</span>')
        else:
            highlighted_content.append(token_text)
        highlighted_content.append(token.whitespace_)

    highlighted_resume = ''.join(highlighted_content)
    return skills, highlighted_resume

def extract_skills(doc):
    skills = []
    for token in doc:
        if token.pos_ in ['NOUN', 'PROPN']:
            skills.append(token.text)
    return skills

def recommend_jobs_with_percentage(skills):
    job_keywords = {
        'Software Developer': ['software', 'developer', 'programming', 'coding'],
        'Data Scientist': ['data', 'scientist', 'analysis', 'statistics'],
        'System Analyst': ['system', 'analyst', 'requirements', 'design'],
        'Marketing': ['marketing', 'advertising', 'campaign', 'strategy'],
        'Blockchain Software Developer': ['React.js', 'Node.js', 'front-end development', 'back-end development','blockchain','etherium','solana'],
        'Database Engineer': ['database management', 'Java', 'Kotlin', 'mobile development'],
        'Mobile Developer - Android': ['Android','android','digital marketing', 'social media marketing','Mobile Developer '],
        'Technical Lead': ['Team Leadership & Management', 'Full Stack Web Development', 'Agile Methodologies', 'Cloud Computing (AWS, Azure)', 'Database Management (SQL, NoSQL)', 'Software Architecture Design', 'Project Planning & Execution', 'Problem-solving & Debugging','Lead','team','Team']
    }
    
    recommended_jobs = []
    
    for job, keywords in job_keywords.items():
        detected_skills = [skill for skill in skills if any(keyword.lower() in skill.lower() for keyword in keywords)]
        if detected_skills:
            percentage_detected = min(len(detected_skills) / len(keywords) * 40, 100)
        else:
            percentage_detected = 0.0  # If no skills detected, set percentage to 0
        
        recommended_jobs.append({'job_title': job, 'percentage_detected': round(percentage_detected, 2)})
    
    return recommended_jobs, job_keywords


def highlight_resume_content(resume_content, job_keywords):
    highlighted_content = resume_content
    colors = {
        'Software Developer': '#ff6f61',
        'Data Scientist': '#ffa500',
        'System Analyst': '#f7ea48',
        'Marketing': '#4caf50',
        'Blockchain Software Developer': '#1e90ff',
        'Database Engineer': '#8a2be2',
        'Mobile Developer - Android': '#ff69b4',
        'Technical Lead': '#20b2aa'
    }

    for job, keywords in job_keywords.items():
        for keyword in keywords:
            highlighted_content = highlighted_content.replace(keyword, f'<span style="background-color: {colors[job]}">{keyword}</span>')
            highlighted_content = highlighted_content.replace(keyword.capitalize(), f'<span style="background-color: {colors[job]}">{keyword.capitalize()}</span>')
    
    return highlighted_content


# Dummy function to check user credentials (replace with actual authentication logic)
def check_user_credentials(email, password):
    with open(USERS_FILE, 'r') as file:
        for line in file:
            stored_email, stored_password = line.strip().split(',')
            if email == stored_email and password == stored_password:
                return True
    return False

# Dummy function to check if user exists (replace with actual logic)
def user_exists(email):
    with open(USERS_FILE, 'r') as file:
        for line in file:
            stored_email, _ = line.strip().split(',')
            if email == stored_email:
                return True
    return False

# Dummy function to save user data (replace with actual logic)
def save_user_data(name, email, password):
    with open(USERS_FILE, 'a') as file:
        file.write(f"{email},{password}\n")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
