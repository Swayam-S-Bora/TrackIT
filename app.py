# app.py

import os
import re
import sqlite3
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functions import *
from predictor import PricePredictionModel
import pandas as pd
import logging
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong, random secret key

# Define the path to the SQLite databases
basedir = os.path.abspath(os.path.dirname(__file__))
users_db_path = os.path.join(basedir, 'users.db')
price_history_db_path = os.path.join(basedir, 'databases_price_history.db')

def get_users_db_connection():
    conn = sqlite3.connect(users_db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_price_history_db_connection():
    conn = sqlite3.connect(price_history_db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_username(email):
    """Extracts the username from an email address."""
    return email.split('@')[0] if '@' in email else email

# Create the `amazon_data` table if it doesn't exist
def initialize_database():
    conn = get_price_history_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS amazon_data (
            srno INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            link TEXT NOT NULL UNIQUE,
            "2024-10-08" INTEGER DEFAULT 0,
            "2024-10-09" INTEGER DEFAULT 0,
            "2024-10-10" INTEGER DEFAULT 0,
            "2024-10-11" INTEGER DEFAULT 0,
            "2024-10-12" INTEGER DEFAULT 0,
            "2024-10-13" INTEGER DEFAULT 0,
            "2024-10-14" INTEGER DEFAULT 0,
            "2024-10-15" INTEGER DEFAULT 0,
            "2024-10-16" INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

initialize_database()


# Initialize Logger
logging.basicConfig(level=logging.INFO)

# Load data and initialize model
try:
    # Connect to the database and load data
    conn = sqlite3.connect(price_history_db_path)
    query = "SELECT * FROM amazon_data"
    dataset = pd.read_sql_query(query, conn)
    conn.close()

    # Initialize prediction model
    predictor = PricePredictionModel(dataset)
    predictor_dataset = predictor.preprocess_data()
    predictor.train_model()  # Train the model with the cleaned dataset

    logging.info("PricePredictionModel initialized successfully.")
except Exception as e:
    logging.error(f"Failed to initialize PricePredictionModel: {e}")
    predictor = None


@app.route('/')
def index():
    return render_template('index.html', title="TrackIT")

@app.route('/scrape', methods=['POST'])
def scrape():
    amazon_product_url = request.form['url']
    amazon_data = scrape_amazon_product(amazon_product_url)
    product_name = amazon_data.get('name', 'N/A')
    current_price = amazon_data['price']
    product_link = amazon_data['link']
    today_date = datetime.now().strftime('%Y-%m-%d')

    prediction = "Prediction unavailable"

    conn = get_price_history_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f'ALTER TABLE amazon_data ADD COLUMN "{today_date}" INTEGER DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass

    prediction_text = "Prediction unavailable"

    try:
        cursor.execute('SELECT * FROM amazon_data WHERE name = ?', (product_name,))
        product = cursor.fetchone()

        if product:
            # Update today's price for the product
            cursor.execute(f'UPDATE amazon_data SET "{today_date}" = ? WHERE name = ?', (current_price, product_name))
            conn.commit()

            # Extract price columns
            product_prices = [product[col] for col in product.keys() if col.startswith("2024-")]

            # Clean and filter numeric prices
            def clean_price(price):
                if isinstance(price, str):
                    price = price.replace('₹', '').replace(',', '').strip()
                try:
                    return float(price)
                except (ValueError, TypeError):
                    return None

            cleaned_prices = [clean_price(price) for price in product_prices if price is not None]

            # Check if sufficient data is available for prediction
            if len(cleaned_prices) >= 2 and predictor:
                avg_price = sum(cleaned_prices) / len(cleaned_prices)
                price_std = (sum((x - avg_price) ** 2 for x in cleaned_prices) / len(cleaned_prices)) ** 0.5
                price_change = (max(cleaned_prices) - min(cleaned_prices)) / max(cleaned_prices)
                input_features = [price_std, price_change]
                try:
                    prediction = predictor.predict(input_features)
                except Exception as e:
                    logging.error(f"Error during prediction: {e}")
                    prediction = -1  # Default value
            else:
                logging.warning("Insufficient data for prediction.")
                prediction = -1  # Default value

            
        else:
            # Insert new product data into the database
            cursor.execute(f'''
                INSERT INTO amazon_data (name, link, "{today_date}")
                VALUES (?, ?, ?)
            ''', (product_name, product_link, current_price))
            conn.commit()

    except Exception as e:
        logging.error(f"Error processing prediction: {e}")


    # Fetch additional details
    flipkart_product_url = find_flipkart_link(product_name)
    flipkart_data = scrape_flipkart_product(flipkart_product_url) if flipkart_product_url else {}
    reliance_product_data = get_first_product_details(product_name)

    conn.close()
    prediction_value = int(prediction) if str(prediction).isdigit() else -1
    return render_template(
        'result.html',
        amazon=amazon_data,
        flipkart=flipkart_data,
        reliance=reliance_product_data,
        prediction=prediction_value
        )
        
@app.route('/track', methods=['POST'])
def track():
    # Get product details from the form
    amazon_link = request.form.get('amazon_link')
    flipkart_link = request.form.get('flipkart_link')
    reliance_link = request.form.get('reliance_link')

    # Extract SRNO from the links
    srno_a = None
    srno_f = None

    if amazon_link:
        srno_a = get_srno_from_link(amazon_link, 'amazon_data')
    if flipkart_link:
        srno_f = get_srno_from_link(flipkart_link, 'flipkart_data')

    if not session.get('user_id'):
        # Store the intended action in session to redirect after login
        session['next'] = request.referrer
        flash('Please log in to track products.', 'warning')
        return redirect(url_for('login'))

    user_email = session.get('email')

    if srno_a:
        add_item(user_email, "srno_a", srno_a)
    if srno_f:
        add_item(user_email, "srno_f", srno_f)

    flash('Product added to your watchlist.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        logging.info(f"Attempting to sign up with email: {email}")  # Debugging statement

        # Validate email format
        email_regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        if not re.match(email_regex, email):
            flash('Invalid email format.', 'danger')
            return render_template('signup.html', title="Sign Up", button_text="Sign Up")

        # Validate password length
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('signup.html', title="Sign Up", button_text="Sign Up")

        conn = get_users_db_connection()
        cursor = conn.cursor()

        # Check if user already exists
        cursor.execute("SELECT * FROM User WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            logging.warning(f"User with email {email} already exists.")
            flash('Email already used. Please log in.', 'warning')
            conn.close()
            return redirect(url_for('login'))

        # Create new user
        try:
            hashed_password = generate_password_hash(password)
            cursor.execute("INSERT INTO User (email, password) VALUES (?, ?)", (email, hashed_password))
            conn.commit()
            logging.info(f"User {email} added to the database.")
            flash('Sign up successful! You can log in now.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash('An error occurred during sign up. Please try again.', 'danger')
            logging.error(f"Error during sign up: {e}")  # For debugging purposes
            return render_template('signup.html', title="Sign Up", button_text="Sign Up")
        finally:
            conn.close()

    return render_template('signup.html', title="Sign Up", button_text="Sign Up")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = get_users_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM User WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['email'] = user['email']  # Store email in session
            flash('Log in successful!', 'success')
            # Redirect to 'next' if exists
            next_page = session.pop('next', None)
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check your email and password.', 'danger')
    return render_template('login.html', title="Log In", button_text="Log In")

@app.route('/dashboard', methods=['GET'])
def dashboard():
    user_id = session.get('user_id')
    user_email = session.get('email')
    if not user_id:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    conn = get_users_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM User WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        flash('User not found. Please log in again.', 'danger')
        return redirect(url_for('login'))

    username = get_username(user['email'])

    # Fetch user's watchlist
    conn_price = get_users_db_connection()
    cursor_price = conn_price.cursor()
    cursor_price.execute("SELECT * FROM user WHERE email = ?", (user_email,))
    watchlist = cursor_price.fetchone()
    conn_price.close()

    watchlist_details = fetch_watchlist_details(watchlist) if watchlist else {'amazon': [], 'flipkart': []}

    return render_template('dashboard.html', username=username, watchlist=watchlist_details)

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    session.pop('email', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

def get_srno_from_link(link, table):
    """Retrieve the srno from the specified table based on the product link."""
    conn = get_price_history_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT srno FROM {table} WHERE link = ?", (link,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result['srno']
    return None

@app.template_filter('fromjson')
def fromjson_filter(json_str):
    """Custom filter to parse JSON strings."""
    try:
        return json.loads(json_str)
    except:
        return []

def fetch_watchlist_details(watchlist):
    """Fetch detailed information about the products in the user's watchlist."""
    watchlist_details = {'amazon': [], 'flipkart': []}
    conn_price = get_users_db_connection()
    cursor_price = conn_price.cursor()

    conn_data = get_price_history_db_connection()
    cursor_data = conn_data.cursor()

    if watchlist['srno_a']:
        try:
            srnos_a = json.loads(watchlist['srno_a'])
            for srno in srnos_a:
                cursor_data.execute("SELECT * FROM amazon_data WHERE srno = ?", (srno,))
                product = cursor_data.fetchone()
                if product:
                    watchlist_details['amazon'].append(product)
        except Exception as e:
            logging.error(f"Error parsing srno_a: {e}")

    if watchlist['srno_f']:
        try:
            srnos_f = json.loads(watchlist['srno_f'])
            for srno in srnos_f:
                cursor_data.execute("SELECT * FROM flipkart_data WHERE srno = ?", (srno,))
                product = cursor_data.fetchone()
                if product:
                    watchlist_details['flipkart'].append(product)
        except Exception as e:
            logging.error(f"Error parsing srno_f: {e}")

    conn_price.close()
    return watchlist_details

# Notification Route (Optional: Trigger manually)
@app.route('/send_notifications', methods=['GET'])
def send_notifications():
    """
    Manual route to trigger notifications.
    You can access this route to send notifications to all users.
    """
    price_drops_amazon = notify("amazon_data")
    price_drops_flipkart = notify("flipkart_data")

    conn_users = get_users_db_connection()
    cursor_users = conn_users.cursor()
    cursor_users.execute("SELECT * FROM user")
    user_carts = cursor_users.fetchall()
    conn_users.close()

    for cart in user_carts:
        user_email = cart['user_mail']
        # Check Flipkart notifications
        if cart['srno_f']:
            srnos_f = json.loads(cart['srno_f'])
            for srno in price_drops_flipkart:
                if srno in srnos_f:
                    send_mail(user_email)
                    break
        # Check Amazon notifications
        if cart['srno_a']:
            srnos_a = json.loads(cart['srno_a'])
            for srno in price_drops_amazon:
                if srno in srnos_a:
                    send_mail(user_email)
                    break

    flash('Notifications have been sent successfully.', 'success')
    return redirect(url_for('dashboard'))

# Route to remove item from watchlist
@app.route('/remove_watchlist', methods=['POST'])
def remove_watchlist():
    user_email = session.get('email')  # Get the logged-in user's email
    platform = request.form.get('platform')  # 'amazon' or 'flipkart'
    srno = request.form.get('srno')  # The serial number of the product to remove

    # Debugging print
    print(f"Form data: {request.form}")
    print(f"Platform: {platform}")
    print(f"Serial Number: {srno}")

    if not user_email:
        flash('Please log in to remove products from your watchlist.', 'warning')
        return redirect(url_for('login'))

    if platform == "amazon":
        columnname = "srno_A"
    elif platform == "flipkart":
        columnname = "srno_f"
    else:
        flash('Invalid platform selected.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        remove_item(user_email, columnname, int(srno))
        flash('Product removed from your watchlist.', 'success')
    except Exception as e:
        print(f"Error during removal: {e}")
        flash('Failed to remove product from your watchlist.', 'danger')

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
# Commit on 2024-12-11T17:41:00+05:30
# Commit on 2024-12-11T19:00:00+05:30
# Commit on 2024-12-11T09:31:00+05:30
# Commit on 2024-12-11T18:32:00+05:30
# Commit on 2024-12-11T11:56:00+05:30
# Commit on 2024-12-11T13:34:00+05:30
# Commit on 2024-12-12T20:57:00+05:30
# Commit on 2024-12-12T18:25:00+05:30
# Commit on 2024-12-12T14:00:00+05:30
# Commit on 2024-12-13T18:54:00+05:30
# Commit on 2024-12-13T14:29:00+05:30
# Commit on 2024-12-13T16:21:00+05:30
# Commit on 2024-12-13T13:58:00+05:30
# Commit on 2024-12-13T19:12:00+05:30
# Commit on 2024-12-14T18:15:00+05:30
# Commit on 2024-12-14T18:42:00+05:30
# Commit on 2024-12-14T12:25:00+05:30
# Commit on 2024-12-14T19:34:00+05:30
# Commit on 2024-12-14T12:00:00+05:30
# Commit on 2024-12-14T16:27:00+05:30
# Commit on 2024-12-16T17:39:00+05:30
# Commit on 2024-12-16T12:45:00+05:30
# Commit on 2024-12-16T10:54:00+05:30
# Commit on 2024-12-16T16:11:00+05:30
# Commit on 2024-12-17T16:20:00+05:30
# Commit on 2024-12-17T13:36:00+05:30
# Commit on 2024-12-17T19:22:00+05:30
# Commit on 2024-12-17T13:11:00+05:30
# Commit on 2024-12-17T09:01:00+05:30
# Commit on 2024-12-17T21:09:00+05:30
# Commit on 2024-12-18T21:32:00+05:30
# Commit on 2024-12-18T13:26:00+05:30
# Commit on 2024-12-18T17:07:00+05:30
# Commit on 2024-12-20T10:24:00+05:30
# Commit on 2024-12-23T09:36:00+05:30
# Commit on 2024-12-23T17:23:00+05:30
# Commit on 2024-12-23T09:58:00+05:30
# Commit on 2024-12-23T21:37:00+05:30
# Commit on 2024-12-24T19:52:00+05:30
# Commit on 2024-12-24T14:28:00+05:30
# Commit on 2024-12-25T09:06:00+05:30
# Commit on 2024-12-25T11:54:00+05:30
# Commit on 2024-12-25T18:38:00+05:30
# Commit on 2024-12-31T11:26:00+05:30
# Commit on 2024-12-31T09:55:00+05:30
# Commit on 2024-12-31T11:10:00+05:30
# Commit on 2025-01-02T09:53:00+05:30
# Commit on 2025-01-02T11:07:00+05:30
# Commit on 2025-01-02T13:24:00+05:30
# Commit on 2025-01-02T12:57:00+05:30
# Commit on 2025-01-02T14:40:00+05:30
# Commit on 2025-01-02T12:40:00+05:30
# Commit on 2025-01-02T11:04:00+05:30
# Commit on 2025-01-02T12:40:00+05:30
# Commit on 2025-01-05T20:10:00+05:30
# Commit on 2025-01-05T20:30:00+05:30
# Commit on 2025-01-06T09:40:00+05:30
# Commit on 2025-01-06T20:18:00+05:30
# Commit on 2025-01-06T12:00:00+05:30
# Commit on 2025-01-06T10:08:00+05:30
# Commit on 2025-01-06T19:38:00+05:30
# Commit on 2025-01-06T11:19:00+05:30
# Commit on 2025-01-08T13:15:00+05:30
# Commit on 2025-01-10T16:34:00+05:30
# Commit on 2025-01-12T09:14:00+05:30
# Commit on 2025-01-12T15:40:00+05:30
# Commit on 2025-01-13T12:05:00+05:30
# Commit on 2025-01-13T13:48:00+05:30
# Commit on 2025-01-13T13:26:00+05:30
# Commit on 2025-01-13T21:37:00+05:30
# Commit on 2025-01-13T20:09:00+05:30
# Commit on 2025-01-13T09:55:00+05:30
# Commit on 2025-01-14T09:12:00+05:30
# Commit on 2025-01-14T14:48:00+05:30
# Commit on 2025-01-14T10:30:00+05:30
# Commit on 2025-01-14T11:31:00+05:30
# Commit on 2025-01-16T16:45:00+05:30
# Commit on 2025-01-16T17:36:00+05:30
# Commit on 2025-01-16T14:44:00+05:30
# Commit on 2025-01-16T11:27:00+05:30
# Commit on 2025-01-16T14:24:00+05:30
# Commit on 2025-01-16T21:23:00+05:30
# Commit on 2025-01-17T19:00:00+05:30
# Commit on 2025-01-17T13:07:00+05:30
# Commit on 2025-01-17T11:10:00+05:30
# Commit on 2025-01-20T09:52:00+05:30
# Commit on 2025-01-23T20:41:00+05:30
# Commit on 2025-01-23T20:01:00+05:30
# Commit on 2025-01-23T13:52:00+05:30
# Commit on 2025-01-23T19:41:00+05:30
# Commit on 2025-01-23T13:03:00+05:30
# Commit on 2025-01-23T17:50:00+05:30
# Commit on 2025-01-23T21:12:00+05:30
# Commit on 2025-01-24T12:16:00+05:30
# Commit on 2025-01-24T21:51:00+05:30
# Commit on 2025-01-24T11:26:00+05:30
# Commit on 2025-01-26T10:11:00+05:30
# Commit on 2025-01-27T19:26:00+05:30
# Commit on 2025-01-27T10:51:00+05:30
# Commit on 2025-01-29T09:07:00+05:30
# Commit on 2025-01-29T19:11:00+05:30
# Commit on 2025-01-29T20:11:00+05:30
# Commit on 2025-01-30T17:08:00+05:30
# Commit on 2025-01-30T09:23:00+05:30
# Commit on 2025-01-30T11:24:00+05:30
# Commit on 2025-01-30T21:18:00+05:30
# Commit on 2025-02-03T14:50:00+05:30
# Commit on 2025-02-03T14:07:00+05:30
# Commit on 2025-02-03T13:34:00+05:30
# Commit on 2025-02-03T10:47:00+05:30
# Commit on 2025-02-03T13:05:00+05:30
# Commit on 2025-02-04T17:51:00+05:30
# Commit on 2025-02-04T09:03:00+05:30
# Commit on 2025-02-04T18:00:00+05:30
# Commit on 2025-02-04T21:17:00+05:30
# Commit on 2025-02-05T11:39:00+05:30
# Commit on 2025-02-05T11:40:00+05:30
# Commit on 2025-02-05T20:05:00+05:30
# Commit on 2025-02-07T14:32:00+05:30
# Commit on 2025-02-07T21:44:00+05:30
# Commit on 2025-02-07T15:00:00+05:30
# Commit on 2025-02-07T19:35:00+05:30
# Commit on 2025-02-07T10:27:00+05:30
# Commit on 2025-02-07T21:37:00+05:30
# Commit on 2025-02-08T18:42:00+05:30
# Commit on 2025-02-10T18:56:00+05:30
# Commit on 2025-02-10T17:33:00+05:30
# Commit on 2025-02-10T12:55:00+05:30
# Commit on 2025-02-10T19:27:00+05:30
# Commit on 2025-02-10T11:50:00+05:30
# Commit on 2025-02-10T20:26:00+05:30
# Commit on 2025-02-11T09:02:00+05:30
# Commit on 2025-02-11T19:47:00+05:30
# Commit on 2025-02-11T14:59:00+05:30
# Commit on 2025-02-11T12:44:00+05:30
# Commit on 2025-02-11T09:42:00+05:30
# Commit on 2025-02-11T20:43:00+05:30
# Commit on 2025-02-12T19:54:00+05:30
# Commit on 2025-02-12T19:20:00+05:30
# Commit on 2025-02-13T16:05:00+05:30
# Commit on 2025-02-13T18:41:00+05:30
# Commit on 2025-02-13T17:46:00+05:30
# Commit on 2025-02-13T13:31:00+05:30
# Commit on 2025-02-13T12:08:00+05:30
# Commit on 2025-02-13T20:21:00+05:30
# Commit on 2025-02-13T11:17:00+05:30
# Commit on 2025-02-14T17:13:00+05:30
# Commit on 2025-02-14T15:26:00+05:30
# Commit on 2025-02-17T21:43:00+05:30
# Commit on 2025-02-18T20:40:00+05:30
# Commit on 2025-02-18T14:47:00+05:30
# Commit on 2025-02-18T19:16:00+05:30
# Commit on 2025-02-18T09:41:00+05:30
# Commit on 2025-02-18T21:58:00+05:30
# Commit on 2025-02-18T13:07:00+05:30
# Commit on 2025-02-18T18:25:00+05:30
# Commit on 2025-02-18T18:45:00+05:30
# Commit on 2025-02-18T10:40:00+05:30
# Commit on 2025-02-19T13:45:00+05:30
# Commit on 2025-02-19T09:56:00+05:30