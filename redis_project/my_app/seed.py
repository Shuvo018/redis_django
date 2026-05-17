import random
from faker import Faker
from .models import Student  # Adjust the import based on your app name

def seed_students(n=500):
    fake = Faker()
    students_to_create = []

    for _ in range(n):
        # Generates a random ID like 'STU-123456'
        stu_id = f"STU-{random.randint(100000, 999999)}"
        stu_name = fake.name()

        # Append a new Student instance to our list
        students_to_create.append(
            Student(stu_id=stu_id, stu_name=stu_name[:50]) # [:50] ensures it fits max_length
        )

    # Efficiently insert all records at once
    Student.objects.bulk_create(students_to_create)
    print(f"Successfully seeded {n} students!")