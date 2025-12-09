# Recalculate Ratings Management Command
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Avg, Count
from core.models import User, MovingService, Review

class Command(BaseCommand):
    help = 'Recalculates ratings for services and users to ensure data consistency.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the command without saving changes to the database.',
        )
        parser.add_argument(
            '--services-only',
            action='store_true',
            help='Recalculate only moving service ratings.',
        )
        parser.add_argument(
            '--users-only',
            action='store_true',
            help='Recalculate only user ratings.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for bulk processing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        services_only = options['services_only']
        users_only = options['users_only']
        batch_size = options['batch_size']

        process_services = not users_only
        process_users = not services_only

        if process_services:
            self.recalculate_services(dry_run, batch_size)

        if process_users:
            self.recalculate_users(dry_run, batch_size)

        if dry_run:
            self.stdout.write(self.style.SUCCESS('Dry run completed. No changes saved.'))
        else:
            self.stdout.write(self.style.SUCCESS('Recalculation completed successfully.'))

    def recalculate_services(self, dry_run, batch_size):
        self.stdout.write('Recalculating service ratings...')
        services = MovingService.objects.all().iterator(chunk_size=batch_size)
        updates = []
        count = 0

        for service in services:
            # Calculate stats for this service
            stats = Review.objects.filter(booking__service=service).aggregate(
                avg_rating=Avg('rating'),
                total=Count('id')
            )
            
            # Ensure new_avg is a Decimal
            raw_avg = stats['avg_rating']
            if raw_avg is None:
                new_avg = Decimal('0.00')
            else:
                new_avg = Decimal(str(raw_avg))
            
            new_total = stats['total'] or 0

            # Check if update is needed
            if abs(service.rating_average - new_avg) > Decimal('0.001') or service.total_reviews != new_total:
                service.rating_average = new_avg
                service.total_reviews = new_total
                updates.append(service)
                
                if dry_run:
                     self.stdout.write(f'  [DRY-RUN] Service {service.id} ({service.service_name}): Rating {service.rating_average} -> {new_avg}, Count {service.total_reviews} -> {new_total}')

            if len(updates) >= batch_size:
                if not dry_run:
                    MovingService.objects.bulk_update(updates, ['rating_average', 'total_reviews'])
                updates = []
            
            count += 1
            if count % 100 == 0:
                self.stdout.write(f'Processed {count} services...')

        if updates and not dry_run:
            MovingService.objects.bulk_update(updates, ['rating_average', 'total_reviews'])
        
        self.stdout.write(f'Processed {count} services total.')

    def recalculate_users(self, dry_run, batch_size):
        self.stdout.write('Recalculating user ratings...')
        users = User.objects.all().iterator(chunk_size=batch_size)
        updates = []
        count = 0

        for user in users:
            updated = False
            
            # 1. Provider Rating
            if user.is_provider():
                # Average of reviews received as provider
                provider_stats = Review.objects.filter(reviewee=user).aggregate(
                    avg=Avg('rating')
                )
                raw_prov_avg = provider_stats['avg']
                if raw_prov_avg is None:
                    new_prov_avg = Decimal('0.00')
                else:
                    new_prov_avg = Decimal(str(raw_prov_avg))
                
                if abs(user.avg_rating_as_provider - new_prov_avg) > Decimal('0.001'):
                    if dry_run:
                         self.stdout.write(f'  [DRY-RUN] User {user.id} (Provider): Rating {user.avg_rating_as_provider} -> {new_prov_avg}')
                    user.avg_rating_as_provider = new_prov_avg
                    updated = True

            # 2. Student Rating
            if user.is_student():
                # Average of reviews received as student
                student_stats = Review.objects.filter(reviewee=user).aggregate(
                    avg=Avg('rating')
                )
                raw_stud_avg = student_stats['avg']
                if raw_stud_avg is None:
                    new_stud_avg = Decimal('0.00')
                else:
                    new_stud_avg = Decimal(str(raw_stud_avg))
                
                if abs(user.avg_rating_as_student - new_stud_avg) > Decimal('0.001'):
                    if dry_run:
                         self.stdout.write(f'  [DRY-RUN] User {user.id} (Student): Rating {user.avg_rating_as_student} -> {new_stud_avg}')
                    user.avg_rating_as_student = new_stud_avg
                    updated = True

            if updated:
                updates.append(user)

            if len(updates) >= batch_size:
                if not dry_run:
                    User.objects.bulk_update(updates, ['avg_rating_as_provider', 'avg_rating_as_student'])
                updates = []
            
            count += 1
            if count % 100 == 0:
                 self.stdout.write(f'Processed {count} users...')

        if updates and not dry_run:
            User.objects.bulk_update(updates, ['avg_rating_as_provider', 'avg_rating_as_student'])

        self.stdout.write(f'Processed {count} users total.')
