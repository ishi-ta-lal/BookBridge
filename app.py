from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc
import math
from datetime import datetime
import pandas as pd
import numpy as np
import os

app = Flask(__name__)
# For testing, you can use SQLite instead of MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///books4all.db'
# Uncomment below to use MySQL (update credentials accordingly)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://username:password@localhost/books4all'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Create a templates directory
os.makedirs('templates', exist_ok=True)

# Define SQLAlchemy models
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    user_type = db.Column(db.String(10))
    organization = db.Column(db.String(100))
    registered_on = db.Column(db.DateTime, default=datetime.utcnow)
    rating = db.Column(db.Integer, default=0)
    no_of_books = db.Column(db.Integer, default=0)
    
    # Define relationships
    books = db.relationship('Book', backref='user', lazy=True)

class Book(db.Model):
    __tablename__ = 'books'
    book_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    title = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    grade_level = db.Column(db.String(50))
    language = db.Column(db.String(50))
    is_donation = db.Column(db.Boolean, default=True)
    condition = db.Column(db.String(50))
    photo_url = db.Column(db.Text)
    listed_on = db.Column(db.DateTime, default=datetime.utcnow)
    fulfilled_qty = db.Column(db.Integer, default=0)
    
    # Define relationships
    donation_matches = db.relationship('Match', foreign_keys='Match.donation_id', backref='donation', lazy=True)
    request_matches = db.relationship('Match', foreign_keys='Match.request_id', backref='request', lazy=True)

class Match(db.Model):
    __tablename__ = 'matches'
    match_id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(db.Integer, db.ForeignKey('books.book_id'))
    request_id = db.Column(db.Integer, db.ForeignKey('books.book_id'))
    matched_qty = db.Column(db.Integer, default=1)
    matched_on = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending')  # Pending, InTransit, Delivered

# Helper function to calculate distance between two addresses
def calculate_distance(address1, address2):
    """
    Calculate distance between two addresses.
    In a production environment, this would use geocoding with Google Maps or similar service.
    
    For demonstration purposes, this is a simplified version that returns a random distance.
    """
    # In a real implementation, you would:
    # 1. Use geocoding API to convert addresses to lat/long coordinates
    # 2. Calculate the distance using Haversine formula
    
    # Simulate distance calculation - replace with actual implementation
    import random
    return random.uniform(0, 30)  # Returns a value between 0-30 km

# Calculate priority score for a school
def calculate_school_priority(rating, no_of_books):
    """
    Calculate priority score for a school based on:
    - Rating: Higher rating = higher priority
    - Books received: Fewer books = higher priority
    
    Returns a score between 0-100 where higher is better
    """
    # Normalize rating to 0-50 (assuming rating is 0-5)
    rating_score = min(rating * 10, 50)
    
    # Inverse relationship with books - fewer books = higher score
    # Use a logarithmic scale to prevent schools with 0 books from getting infinite priority
    books_factor = 50 * max(0, (1 - (math.log(no_of_books + 1) / 10)))
    
    return rating_score + books_factor

# Core matching algorithm
def run_matching_algorithm():
    """
    Main matching algorithm that:
    1. Finds all active donations and requests
    2. Scores possible matches based on proximity and school priority
    3. Creates optimal matches in descending order of score
    4. Updates database with new matches
    """
    # Step 1: Get all active donations and requests using SQLAlchemy
    donations = Book.query.filter(
        Book.is_donation == True,
        Book.quantity > Book.fulfilled_qty
    ).all()
    
    requests = Book.query.filter(
        Book.is_donation == False,
        Book.quantity > Book.fulfilled_qty
    ).all()
    
    # Early return if no matches possible
    if not donations or not requests:
        return {"message": "No active donations or requests found for matching"}, 404
    
    # Step 2: Build compatibility matrix with SQLAlchemy relationships
    matches = []
    
    for donation in donations:
        donor = donation.user  # Use SQLAlchemy relationship
        available_qty = donation.quantity - donation.fulfilled_qty
        
        if available_qty <= 0:
            continue
            
        for request in requests:
            school = request.user  # Use SQLAlchemy relationship
            needed_qty = request.quantity - request.fulfilled_qty
            
            if needed_qty <= 0:
                continue
                
            # Skip if basic attributes don't match
            if donation.title.lower() != request.title.lower() and request.title.lower() != "any":
                continue
                
            if donation.grade_level != request.grade_level and request.grade_level != "any":
                continue
                
            if donation.language != request.language and request.language != "any":
                continue
            
            # Calculate match score components
            distance = calculate_distance(donor.address, school.address)
            proximity_score = max(0, 100 - (distance * 3))  # 0 km = 100 points, 30+ km = 0 points
            
            school_priority = calculate_school_priority(school.rating, school.no_of_books)
            
            # Calculate final match score (0-100)
            match_score = (proximity_score * 0.7) + (school_priority * 0.3)
            
            # Determine match quantity
            match_qty = min(available_qty, needed_qty)
            
            matches.append({
                'donation_id': donation.book_id,
                'request_id': request.book_id,
                'donor_id': donor.user_id,
                'school_id': school.user_id,
                'match_qty': match_qty,
                'match_score': match_score,
                'proximity_score': proximity_score,
                'school_priority': school_priority,
                'distance': distance
            })
    
    # Step 3: Sort by match score and create optimal matches
    if not matches:
        return {"message": "No compatible matches found between donations and requests"}, 404
    
    # Convert to pandas DataFrame for easier manipulation
    matches_df = pd.DataFrame(matches)
    
    # Sort by match score in descending order
    matches_df = matches_df.sort_values('match_score', ascending=False)
    
    # Keep track of remaining quantities
    donation_remaining = {d.book_id: d.quantity - d.fulfilled_qty for d in donations}
    request_remaining = {r.book_id: r.quantity - r.fulfilled_qty for r in requests}
    
    # Final matches to be created
    final_matches = []
    
    # Process matches in order of score
    for _, match in matches_df.iterrows():
        donation_id = match['donation_id']
        request_id = match['request_id']
        
        # Skip if either donation or request is already fully matched
        if donation_remaining[donation_id] <= 0 or request_remaining[request_id] <= 0:
            continue
        
        # Calculate quantity that can be matched
        match_qty = min(donation_remaining[donation_id], request_remaining[request_id])
        
        if match_qty > 0:
            final_matches.append({
                'donation_id': int(donation_id),
                'request_id': int(request_id),
                'matched_qty': int(match_qty),
                'matched_on': datetime.utcnow(),
                'status': 'Pending'
            })
            
            # Update remaining quantities
            donation_remaining[donation_id] -= match_qty
            request_remaining[request_id] -= match_qty
    
    # Step 4: Create match records in database using SQLAlchemy ORM
    created_matches = []
    for match_data in final_matches:
        # Create new match record
        new_match = Match(
            donation_id=match_data['donation_id'],
            request_id=match_data['request_id'],
            matched_qty=match_data['matched_qty'],
            matched_on=match_data['matched_on'],
            status=match_data['status']
        )
        db.session.add(new_match)
        
        # Update fulfilled quantities for donation and request
        donation = Book.query.get(match_data['donation_id'])
        donation.fulfilled_qty += match_data['matched_qty']
        
        request = Book.query.get(match_data['request_id'])
        request.fulfilled_qty += match_data['matched_qty']
        
        # Get user information for the response
        donor = User.query.get(donation.user_id)
        school = User.query.get(request.user_id)
        
        # Create response object with more details
        created_matches.append({
            'match_id': None,  # Will be set after commit
            'donation_id': donation.book_id,
            'request_id': request.book_id,
            'matched_qty': match_data['matched_qty'],
            'book_title': donation.title,
            'donor_name': donor.name,
            'school_name': school.organization
        })
    
    # Commit all changes in a single transaction
    try:
        db.session.commit()
        
        # Now that we have committed, we can get the match IDs
        for i, match_data in enumerate(created_matches):
            # Get the match ID from the database
            match = Match.query.filter_by(
                donation_id=match_data['donation_id'], 
                request_id=match_data['request_id'],
                matched_qty=match_data['matched_qty']
            ).order_by(Match.matched_on.desc()).first()
            
            if match:
                created_matches[i]['match_id'] = match.match_id
        
        return {"matches_created": len(created_matches), "matches": created_matches}, 200
    
    except Exception as e:
        db.session.rollback()
        return {"error": str(e)}, 500

# API endpoint to trigger matching
@app.route('/api/run-matching', methods=['POST'])
def api_run_matching():
    result, status_code = run_matching_algorithm()
    return jsonify(result), status_code

# API endpoint to get matches for a school
@app.route('/api/school/<int:school_id>/matches', methods=['GET'])
def get_school_matches(school_id):
    # Get all book requests by this school using relationships
    school_books = Book.query.filter_by(user_id=school_id, is_donation=False).all()
    
    matches_list = []
    for book in school_books:
        # Use the relationship to get matches
        for match in book.request_matches:
            # Get the donation and donor using relationships
            donation = match.donation
            donor = User.query.get(donation.user_id)
            
            matches_list.append({
                'match_id': match.match_id,
                'book_title': donation.title,
                'quantity': match.matched_qty,
                'donor_name': donor.name,
                'donor_id': donor.user_id,
                'status': match.status,
                'matched_on': match.matched_on.strftime('%Y-%m-%d %H:%M:%S')
            })
    
    return jsonify({"school_id": school_id, "matches": matches_list})

# API endpoint to get matches for a donor
@app.route('/api/donor/<int:donor_id>/matches', methods=['GET'])
def get_donor_matches(donor_id):
    # Get all donations by this donor using relationships
    donor_books = Book.query.filter_by(user_id=donor_id, is_donation=True).all()
    
    matches_list = []
    for book in donor_books:
        # Use the relationship to get matches
        for match in book.donation_matches:
            # Get the request and school using relationships
            request = match.request
            school = User.query.get(request.user_id)
            
            matches_list.append({
                'match_id': match.match_id,
                'book_title': book.title,
                'quantity': match.matched_qty,
                'school_name': school.organization,
                'school_id': school.user_id,
                'status': match.status,
                'matched_on': match.matched_on.strftime('%Y-%m-%d %H:%M:%S')
            })
    
    return jsonify({"donor_id": donor_id, "matches": matches_list})

# Optional: Endpoint to manually update match status
@app.route('/api/match/<int:match_id>/status', methods=['PUT'])
def update_match_status(match_id):
    new_status = request.json.get('status')
    if not new_status:
        return jsonify({"error": "Status not provided"}), 400
        
    match = Match.query.get(match_id)
    if not match:
        return jsonify({"error": "Match not found"}), 404
        
    valid_statuses = ['Pending', 'InTransit', 'Delivered', 'Cancelled']
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
    
    match.status = new_status
    
    # If status is "Delivered", update the school's book count
    if new_status == 'Delivered':
        request = Book.query.get(match.request_id)
        school = User.query.get(request.user_id)
        school.no_of_books += match.matched_qty
        
    try:
        db.session.commit()
        return jsonify({"match_id": match_id, "status": new_status}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Frontend Routes
@app.route('/')
def index():
    # Get all users for the dropdown menus
    donors = User.query.filter_by(user_type='donor').all()
    schools = User.query.filter_by(user_type='school').all()
    
    # Get active donations and requests
    donations = Book.query.filter_by(is_donation=True).all()
    requests = Book.query.filter_by(is_donation=False).all()
    
    # Get all matches
    matches = Match.query.all()
    
    return render_template('index.html', 
                          donors=donors, 
                          schools=schools, 
                          donations=donations, 
                          requests=requests, 
                          matches=matches)

@app.route('/run-matching-ui', methods=['POST'])
def run_matching_ui():
    result, _ = run_matching_algorithm()
    return redirect(url_for('index'))

@app.route('/update-status/<int:match_id>', methods=['POST'])
def update_status_ui(match_id):
    new_status = request.form.get('status')
    match = Match.query.get(match_id)
    if match and new_status:
        match.status = new_status
        
        # If status is "Delivered", update the school's book count
        if new_status == 'Delivered':
            request_book = Book.query.get(match.request_id)
            school = User.query.get(request_book.user_id)
            school.no_of_books += match.matched_qty
            
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/view-donor/<int:donor_id>')
def view_donor(donor_id):
    donor = User.query.get(donor_id)
    matches = []
    
    if donor:
        donor_books = Book.query.filter_by(user_id=donor_id, is_donation=True).all()
        
        for book in donor_books:
            for match in book.donation_matches:
                request_book = match.request
                school = User.query.get(request_book.user_id)
                
                matches.append({
                    'match_id': match.match_id,
                    'book_title': book.title,
                    'quantity': match.matched_qty,
                    'school_name': school.organization,
                    'status': match.status,
                    'matched_on': match.matched_on.strftime('%Y-%m-%d %H:%M:%S')
                })
    
    return render_template('donor.html', donor=donor, matches=matches)

@app.route('/view-school/<int:school_id>')
def view_school(school_id):
    school = User.query.get(school_id)
    matches = []
    
    if school:
        school_books = Book.query.filter_by(user_id=school_id, is_donation=False).all()
        
        for book in school_books:
            for match in book.request_matches:
                donation = match.donation
                donor = User.query.get(donation.user_id)
                
                matches.append({
                    'match_id': match.match_id,
                    'book_title': donation.title,
                    'quantity': match.matched_qty,
                    'donor_name': donor.name,
                    'status': match.status,
                    'matched_on': match.matched_on.strftime('%Y-%m-%d %H:%M:%S')
                })
    
    return render_template('school.html', school=school, matches=matches)

if __name__ == '__main__':
    app.run(debug=True)