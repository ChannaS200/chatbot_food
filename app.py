from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
import os
import pandas as pd

from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your actual secret key


UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

model = load_model('food_images_VGG16_model.h5')  # Adjust path if needed
class_labels = ['Apple', 'Banana', 'Biscuit', 'Bread', 'Broccoli', 'Burger', 'Cake', 'Carrot', 'Cheese', 'Chicken', 'Chocolate', 'Coffee', 'Egg', 'Fish', 'French_Fries', 'Fruit_Juice', 'Ice_Cream', 'Marsh_Mellow', 'Milk_glass', 'Oats', 'Orange', 'Pasta', 'Pizza', 'Potato', 'Rice', 'Soft_Drinks', 'Spinach', 'Tomato', 'Yogurt']
  # Update to match your model's classes
calorie_data = pd.read_excel("static/data/food_calorie_estimates.xlsx")



# MySQL Configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'dietdb'

mysql = MySQL(app)


@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')


# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()
        if account:
            flash('Account already exists!', 'danger')
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Invalid email address!', 'danger')
        else:
            cursor.execute('INSERT INTO users (name, email, mobile, password) VALUES (%s, %s, %s, %s)',
                           (name, email, mobile, password))
            mysql.connection.commit()
            flash('You have successfully registered!', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


# Login Route
from flask import Flask, render_template, request, redirect, url_for, session, flash
import MySQLdb.cursors

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
        user = cursor.fetchone()

        if user:
            session['loggedin'] = True
            session['id'] = user['id']
            session['name'] = user['name']
            session['email'] = user['email']
            return redirect(url_for('dashboard'))
        else:
            flash('Incorrect email or password!', 'danger')

    return render_template('login.html')




# Dashboard Route
@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        return render_template('dashboard.html', name=session['name'], email=session['email'])
    return redirect(url_for('login'))

# TDEE Route
@app.route('/tdee')
def show_tdee():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM medical_records WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (session['id'],))
    record = cursor.fetchone()

    if record:
        tdee = calculate_tdee(record['gender'], record['age'], record['height_cm'], record['weight_kg'], record['activity_level'])
        return render_template('tdee_result.html', tdee=round(tdee), goal=record['goal'])
    else:
        flash("No medical record found!", "warning")
        return redirect(url_for('medical_records'))


# Update Profile
@app.route('/update', methods=['GET', 'POST'])
def update_profile():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_name = request.form['name']
        new_mobile = request.form['mobile']
        cursor = mysql.connection.cursor()
        cursor.execute('UPDATE users SET name = %s, mobile = %s WHERE id = %s',
                       (new_name, new_mobile, session['id']))
        mysql.connection.commit()
        session['name'] = new_name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('update_profile.html', name=session['name'])
#medical record
def calculate_tdee(gender, age, height, weight, activity):
    # Harris-Benedict BMR
    if gender == 'Male':
        bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
    else:
        bmr = 447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age)

    activity_factors = {
        'Sedentary': 1.2,
        'Lightly Active': 1.375,
        'Moderately Active': 1.55,
        'Very Active': 1.725,
        'Extra Active': 1.9
    }
    return bmr * activity_factors.get(activity, 1.2)

@app.route('/medical_records', methods=['GET', 'POST'])
def medical_records():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        form = request.form
        diabetic = form['diabetic']
        cholesterol = form['cholesterol']
        pressure = form['pressure']
        age = int(form['age'])
        gender = form['gender']
        height = float(form['height_cm'])
        weight = float(form['weight_kg'])
        goal = form['goal']
        activity = form['activity_level']
        user_id = session['id']

        tdee = calculate_tdee(gender, age, height, weight, activity)

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO medical_records (user_id, diabetic_level, cholesterol_level, pressure_level, 
                                          age, gender, height_cm, weight_kg, goal, activity_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, diabetic, cholesterol, pressure, age, gender, height, weight, goal, activity))
        mysql.connection.commit()

        session['tdee'] = round(tdee, 2)  # Save to session if needed
        flash(f'Medical record added successfully! Your estimated TDEE is {round(tdee)} calories/day.', 'success')
        return redirect(url_for('show_tdee'))

    return render_template('medical_records.html')


#view record
@app.route('/view_records')
def view_records():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    user_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM medical_records WHERE user_id = %s ORDER BY created_at DESC', (user_id,))
    records = cursor.fetchall()

    return render_template('view_records.html', records=records)

#upload image
@app.route('/classify', methods=['GET', 'POST'])
def classify_image():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    prediction = None
    image_url = None
    calorie_info = {}

    if request.method == 'POST':
        file = request.files['image']
        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            image_url = url_for('static', filename='uploads/' + file.filename)

            # Preprocess image
            img = image.load_img(filepath, target_size=(224, 224))
            img_array = image.img_to_array(img)
            img_array = np.expand_dims(img_array, axis=0)
            img_array /= 255.0

            result = model.predict(img_array)
            predicted_class = class_labels[np.argmax(result)]
            prediction = f"Predicted class: {predicted_class}"
            session['last_food'] = predicted_class


            # Get calorie info from Excel
            row = calorie_data[calorie_data['Food'] == predicted_class]
            if not row.empty:
                calorie_info = {
                    'calories_100g': row.iloc[0]['Calories_per_100g'],
                    'serving_size': row.iloc[0]['Serving_Size'],
                    'calories_per_serving': row.iloc[0]['Calories_per_Serving']
                }

    return render_template('classify.html',
                           prediction=prediction,
                           image_url=image_url,
                           calorie_info=calorie_info)




# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

#cahtbot
from flask import request, jsonify

@app.route('/chatbot_api', methods=['POST'])
def chatbot_api():
    user_msg = request.json['message'].lower()
    reply = "I'm here to help with food, diet, and calories. Try asking about those!"

    # Get the latest predicted food class
    food_item = session.get('last_food')

    # Get the latest medical record for this user
    user_id = session.get('id')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM medical_records WHERE user_id = %s ORDER BY created_at DESC LIMIT 1', (user_id,))
    medical = cursor.fetchone()

    if "should i eat" in user_msg or "can i eat" in user_msg:
        if food_item and medical:
            diabetic = float(medical['diabetic_level'])
            cholesterol = float(medical['cholesterol_level'])
            pressure = float(medical['pressure_level'])

            unhealthy_foods = []

            # Basic rule logic (you can improve with thresholds)
            if diabetic > 140 and food_item in ['Cake', 'Chocolate', 'Soft_Drinks']:
                unhealthy_foods.append("high sugar")
            if cholesterol > 200 and food_item in ['Cheese', 'Burger', 'Chicken']:
                unhealthy_foods.append("high cholesterol")
            if pressure > 130 and food_item in ['Salted Chips', 'Pizza']:
                unhealthy_foods.append("high salt")

            if unhealthy_foods:
                reply = f"{food_item} is not recommended for you due to its {', '.join(unhealthy_foods)} content."
            else:
                reply = f"{food_item} seems okay based on your current medical records. Just don't overeat!"
        else:
            reply = "Please upload a food image and add your medical record first."

    elif "calorie" in user_msg and food_item:
        row = calorie_data[calorie_data['Food'] == food_item]
        if not row.empty:
            reply = f"{food_item} contains {row.iloc[0]['Calories_per_Serving']} calories per serving."
        else:
            reply = "Sorry, I couldn’t find calorie info for that food."

    elif "hi" in user_msg or "hello" in user_msg:
        reply = "Hello! Upload a food image and let me know if it's good for you based on your health."

    return jsonify({"reply": reply})



# Run the App
if __name__ == '__main__':
    app.run(debug=True)
