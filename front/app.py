import sys
import os
from flask import Flask, render_template, flash, redirect, url_for, request, jsonify
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
# from backend.api import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.api import get_articles, retrieve_all, format_results, gpt_output
from front.forms import RegistrationForm, LoginForm
from front.models import User
from front.db import db
# Add the backend directory to the system path
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
# from api import retrieve_all, format_results, gpt_output, get_articles

app = Flask(__name__, static_folder='styles')
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

# Initialize SQLAlchemy
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Route for the home page
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('search'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('search'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('This email address is already registered. ' +
                  'Please <a href="{}">login</a> instead.'.format(url_for('login')), 'danger')
            return redirect(url_for('login')) 
        new_user = User(username=form.username.data, email=form.email.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()  
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# Route for search functionality
@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form['query']  # Get the search query from the form
        raw_results = retrieve_all(query)  # Get raw results from API
        results = format_results(raw_results)  # Format the results
        return render_template('search_results.html', query=query, results=results)
    return render_template('search.html')  # Render the search page template

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()  # Get the JSON data from the request
    user_message = data.get('message')  # Extract the user's message
    bot_response = gpt_output(user_message)  # Get the chatbot's response
    return jsonify({"response": bot_response})  # Return the response as JSON


@app.route('/database')
def database():
    articles = get_articles()
    return render_template('database.html', articles=articles, enumerate=enumerate)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")

