from app import app, db, User, Book, Match
from datetime import datetime

def setup_database():
    with app.app_context():
        # Create all tables
        db.drop_all()  # Be careful with this in production!
        db.create_all()
        
        # Create mock users (donors and schools)
        donor1 = User(
            name="John Donor",
            email="john@example.com",
            phone="123-456-7890",
            address="123 Main St, City A",
            user_type="donor",
            organization="Individual",
            registered_on=datetime.utcnow(),
            rating=5,
            no_of_books=0
        )
        
        donor2 = User(
            name="Jane Donor",
            email="jane@example.com",
            phone="098-765-4321",
            address="456 Oak St, City B",
            user_type="donor",
            organization="Book Club",
            registered_on=datetime.utcnow(),
            rating=4,
            no_of_books=0
        )
        
        school1 = User(
            name="Principal Smith",
            email="smith@school.edu",
            phone="111-222-3333",
            address="789 School Ave, City A",
            user_type="school",
            organization="City Elementary School",
            registered_on=datetime.utcnow(),
            rating=4,
            no_of_books=5
        )
        
        school2 = User(
            name="Principal Johnson",
            email="johnson@school.edu",
            phone="444-555-6666",
            address="101 Education Blvd, City C",
            user_type="school",
            organization="Rural High School",
            registered_on=datetime.utcnow(),
            rating=3,
            no_of_books=2
        )
        
        db.session.add_all([donor1, donor2, school1, school2])
        db.session.commit()
        
        # Create mock book donations
        donation1 = Book(
            user_id=donor1.user_id,
            title="Math Textbook Grade 5",
            quantity=10,
            grade_level="Elementary",
            language="English",
            is_donation=True,
            condition="Good",
            photo_url="https://example.com/math.jpg",
            listed_on=datetime.utcnow(),
            fulfilled_qty=0
        )
        
        donation2 = Book(
            user_id=donor2.user_id,
            title="Science Encyclopedia",
            quantity=5,
            grade_level="Middle",
            language="English",
            is_donation=True,
            condition="Excellent",
            photo_url="https://example.com/science.jpg",
            listed_on=datetime.utcnow(),
            fulfilled_qty=0
        )
        
        donation3 = Book(
            user_id=donor1.user_id,
            title="Children's Story Collection",
            quantity=15,
            grade_level="Elementary",
            language="Spanish",
            is_donation=True,
            condition="Fair",
            photo_url="https://example.com/stories.jpg",
            listed_on=datetime.utcnow(),
            fulfilled_qty=0
        )
        
        # Create mock book requests
        request1 = Book(
            user_id=school1.user_id,
            title="Math Textbook Grade 5",
            quantity=8,
            grade_level="Elementary",
            language="English",
            is_donation=False,
            condition="Any",
            listed_on=datetime.utcnow(),
            fulfilled_qty=0
        )
        
        request2 = Book(
            user_id=school2.user_id,
            title="Science Encyclopedia",
            quantity=3,
            grade_level="Middle",
            language="English",
            is_donation=False,
            condition="Any",
            listed_on=datetime.utcnow(),
            fulfilled_qty=0
        )
        
        # request3 = Book(
        #     user_id=school2.user_id,
        #     title="Children's Story Collection",
        #     quantity=10,
        #     grade_level="Elementary",
        #     language="Spanish",
        #     is_donation=False,
        #     condition="Any",
        #     listed_on=datetime.utcnow(),
        #     fulfilled_qty=0
        # )
        
        # db.session.add_all([donation1, donation2, donation3, request1, request2, request3])
        db.session.add_all([donation1, donation2, donation3, request1, request2])

        db.session.commit()
        
        print("Database setup complete with mock data!")
        print(f"Created {User.query.count()} users")
        print(f"Created {Book.query.filter_by(is_donation=True).count()} donations")
        print(f"Created {Book.query.filter_by(is_donation=False).count()} requests")

if __name__ == "__main__":
    setup_database()