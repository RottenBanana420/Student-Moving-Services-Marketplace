import os
import sys
import django
import random
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from faker import Faker

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'student_moving_marketplace.settings')
django.setup()

from core.models import (
    User, MovingService, Booking, FurnitureItem, 
    FurnitureImage, FurnitureTransaction, Review
)

fake = Faker()

def create_users(num_students=10, num_providers=5):
    print(f"Creating {num_students} students and {num_providers} providers...")
    
    students = []
    providers = []
    
    # Create Students
    for _ in range(num_students):
        email = fake.unique.email()
        username = email.split('@')[0]
        user = User.objects.create_user(
            username=username,
            email=email,
            password='password123',
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            phone_number=fake.phone_number()[:20],
            university_name=fake.company(),
            user_type='student'
        )
        students.append(user)
        
    # Create Providers
    for _ in range(num_providers):
        email = fake.unique.email()
        username = email.split('@')[0]
        user = User.objects.create_user(
            username=username,
            email=email,
            password='password123',
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            phone_number=fake.phone_number()[:20],
            user_type='provider',
            is_verified=random.choice([True, False])
        )
        providers.append(user)
        
    print(f"Created {len(students)} students and {len(providers)} providers.")
    return students, providers

def create_moving_services(providers):
    print("Creating moving services...")
    services = []
    
    service_names = [
        "Local Move", "Long Distance Move", "Furniture Assembly", 
        "Packing Service", "Storage Solutions", "Van Rental with Driver"
    ]
    
    for provider in providers:
        # Each provider offers 1-3 services
        num_services = random.randint(1, 3)
        provider_services = random.sample(service_names, num_services)
        
        for service_name in provider_services:
            service = MovingService.objects.create(
                provider=provider,
                service_name=service_name,
                description=fake.paragraph(),
                base_price=Decimal(random.uniform(50.0, 500.0)).quantize(Decimal('0.01')),
                availability_status=True,
                rating_average=Decimal(random.uniform(3.5, 5.0)).quantize(Decimal('0.01')),
                total_reviews=random.randint(0, 50)
            )
            services.append(service)
            
    print(f"Created {len(services)} moving services.")
    return services

def create_bookings(students, services):
    print("Creating bookings...")
    bookings = []
    
    statuses = ['pending', 'confirmed', 'completed', 'cancelled']
    
    for student in students:
        # Each student makes 0-3 bookings
        num_bookings = random.randint(0, 3)
        
        for _ in range(num_bookings):
            service = random.choice(services)
            status = random.choice(statuses)
            
            # Date logic
            if status == 'completed':
                booking_date = timezone.now() - timedelta(days=random.randint(1, 30))
            else:
                booking_date = timezone.now() + timedelta(days=random.randint(1, 30))
                
            booking = Booking.objects.create(
                student=student,
                provider=service.provider,
                service=service,
                booking_date=booking_date,
                pickup_location=fake.address(),
                dropoff_location=fake.address(),
                status=status,
                total_price=service.base_price + Decimal(random.uniform(10.0, 100.0)).quantize(Decimal('0.01'))
            )
            bookings.append(booking)
            
    print(f"Created {len(bookings)} bookings.")
    return bookings

def create_reviews(bookings):
    print("Creating reviews...")
    reviews = []
    
    completed_bookings = [b for b in bookings if b.status == 'completed']
    
    for booking in completed_bookings:
        # 70% chance of leaving a review
        if random.random() < 0.7:
            # Student reviews provider
            review = Review.objects.create(
                reviewer=booking.student,
                reviewee=booking.provider,
                booking=booking,
                rating=random.randint(3, 5),
                comment=fake.paragraph()
            )
            reviews.append(review)
            
    print(f"Created {len(reviews)} reviews.")
    return reviews

def create_furniture_items(users):
    print("Creating furniture items...")
    items = []
    
    conditions = ['new', 'like_new', 'good', 'fair', 'poor']
    categories = ['furniture', 'appliances', 'electronics', 'books', 'clothing', 'other']
    
    furniture_titles = [
        "Sofa", "Dining Table", "Study Desk", "Office Chair", "Bed Frame", 
        "Bookshelf", "Microwave", "Mini Fridge", "Lamp", "Coffee Table"
    ]
    
    for user in users:
        # Each user sells 0-2 items
        num_items = random.randint(0, 2)
        
        for _ in range(num_items):
            title = random.choice(furniture_titles)
            item = FurnitureItem.objects.create(
                seller=user,
                title=f"{random.choice(['Vintage', 'Modern', 'Used', 'Brand New'])} {title}",
                description=fake.text(),
                price=Decimal(random.uniform(10.0, 300.0)).quantize(Decimal('0.01')),
                condition=random.choice(conditions),
                category=random.choice(categories),
                is_sold=False
            )
            items.append(item)
            
    print(f"Created {len(items)} furniture items.")
    return items

def create_furniture_transactions(users, items):
    print("Creating furniture transactions...")
    transactions = []
    
    # Filter available items
    available_items = [i for i in items if not i.is_sold]
    
    # Create some transactions
    num_transactions = min(len(available_items), len(users)) // 2
    
    for _ in range(num_transactions):
        if not available_items:
            break
            
        item = available_items.pop()
        buyer = random.choice([u for u in users if u != item.seller])
        
        status = random.choice(['pending', 'held', 'released'])
        
        transaction = FurnitureTransaction.objects.create(
            buyer=buyer,
            seller=item.seller,
            furniture_item=item,
            escrow_status=status
        )
        
        if status == 'released':
            transaction.completed_at = timezone.now()
            transaction.save()
            item.mark_as_sold()
            
        transactions.append(transaction)
        
    print(f"Created {len(transactions)} furniture transactions.")
    return transactions

def main():
    print("Starting database population...")
    
    # Create Users
    students, providers = create_users(num_students=20, num_providers=10)
    all_users = students + providers
    
    # Create Services
    services = create_moving_services(providers)
    
    # Create Bookings
    bookings = create_bookings(students, services)
    
    # Create Reviews
    create_reviews(bookings)
    
    # Create Furniture Items
    items = create_furniture_items(all_users)
    
    # Create Furniture Transactions
    create_furniture_transactions(all_users, items)
    
    print("Database population completed successfully!")

if __name__ == '__main__':
    main()
