# 🚀 Redis + Django — Practical Power Guide

A hands-on Django project demonstrating real-world Redis patterns: **caching**, **rate limiting**, **leaderboards**, and **handling massive concurrent registrations** with background workers.

---

## 📌 Table of Contents

- [What is Redis & Why Do We Need It?](#-what-is-redis--why-do-we-need-it)
- [Environment Setup](#-environment-setup)
- [Features & Code Walkthrough](#-features--code-walkthrough)
  - [Caching](#1-caching)
  - [Rate Limiting](#2-rate-limiting)
  - [Leaderboard](#3-leaderboard)
  - [Massive Student Registration](#4-massive-student-registration)
- [Project Structure](#-project-structure)

---

## ⚡ What is Redis & Why Do We Need It?

**Redis** (Remote Dictionary Server) is an open-source, **in-memory data structure store** used as a database, cache, message broker, and queue. It stores data in RAM, making reads and writes **blazing fast** — often sub-millisecond.

### Why Redis?

| Problem | Without Redis | With Redis |
|---|---|---|
| Repeated DB queries | Hits PostgreSQL every time | Returns cached result instantly |
| API abuse / DDoS | No protection | Rate limit per IP/user |
| Live rankings | Slow ORDER BY queries | O(log N) sorted sets |
| Thousands of signups | App crashes under load | Queued via background workers |

> **TL;DR:** Redis sits between your Django app and your database, handling speed-critical and high-concurrency tasks that your database was never designed for.

---

## 🛠 Environment Setup

### Prerequisites

- Python 3.10+
- Redis Server
- pip / virtualenv

### 1. Clone the Repository

```bash
git clone https://github.com/Shuvo018/redis_django.git
cd redis_django
```

### 2. Create & Activate Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Core packages used:**
> ```
> Django
> redis
> django-redis
> celery
> django-ratelimit
> ```

### 4. Install & Start Redis Server

```bash
# WSL - Ubuntu

sudo apt-get install redis-server
sudo service redis-server start

# Verify Redis is running
redis-cli ping   # → PONG
```

### 5. Configure Django Settings

Add this to your `settings.py`:

```python
# settings.py

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

```

### 6. Run Migrations & Start Server

```bash
python manage.py migrate
python manage.py runserver
```

---

## 🔧 Features & Code Walkthrough

### 1. Caching

**Problem:** Every time a user visits a page, Django queries the database. If 1000 users hit the same endpoint simultaneously, that's 1000 DB queries.

**Solution:** Cache the result in Redis for a set duration. Subsequent requests return the cached value instantly — no DB query needed.

```python
# views.py

import redis
from django.core.cache import cache
from django.http import JsonResponse
from .models import Student

r = redis.StrictRedis(host='localhost', port=6379, db=0)

def get_student_list(request):
    cache_key = "student_list"
    cached_data = cache.get(cache_key)

    if cached_data:
        # ✅ Cache HIT — return instantly from Redis
        return JsonResponse({"source": "cache", "data": cached_data})

    # ❌ Cache MISS — query the database
    students = list(Student.objects.values("id", "name", "email"))
    cache.set(cache_key, students, timeout=60 * 5)  # Cache for 5 minutes

    return JsonResponse({"source": "database", "data": students})
```

**How it works:**
- `cache.get(cache_key)` — checks Redis first.
- On a **cache miss**, the DB is queried and the result stored in Redis with a 5-minute TTL.
- On a **cache hit**, Redis returns the result in ~1ms — no DB touch.

---

### 2. Rate Limiting

**Problem:** Without limits, a single client can spam your API with thousands of requests per second, causing a denial-of-service.

**Solution:** Track request counts per IP (or user) in Redis. If the count exceeds the threshold within the time window, reject the request with HTTP 429.

```python
# rate_limit.py

def rate_limit(max_request: int, time_window: int):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            request = args[0] if hasattr(args[0], 'user') else args[1]
            
            client_id = request.user.id if request.user.is_authenticated else request.META.get('REMOTE_ADDR')
            endpoint = request.path
            redis_key = f'rate_limit:{client_id}:{endpoint}'

            current_requests = redis_client.get(redis_key)

            if current_requests is None:
                redis_client.set(redis_key, 1, ex=time_window)
            elif int(current_requests) < max_request:
                redis_client.incr(redis_key)
            else:
                retry_after = redis_client.ttl(redis_key)
                raise Throttled(detail=f"Rate limit exceeded. Try again after {retry_after} seconds.")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

# views.py

# 5 request in 1 minute 
@rate_limit(max_request=5, time_window=60)
def list_view(request):
    cache_key = 'students-data'

    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return Response({"message": cached_data})
    
    data = list(Student.objects.all().values('stu_id', 'stu_name'))
    
    cache.set(cache_key, data, 60 * 5)
    return Response({"message": data})


```


### 3. Leaderboard

**Problem:** Maintaining a ranked list (top students by score) with SQL requires expensive `ORDER BY` + `RANK()` queries at scale.

**Solution:** Redis **Sorted Sets** (`ZSET`) keep scores ordered automatically. Adding, updating, and retrieving ranked entries is O(log N).

```python
# views.py

import redis
from django.http import JsonResponse

r = redis.StrictRedis(host='localhost', port=6379, db=0)

LEADERBOARD_KEY = "student:leaderboard"

def add_score(request, student_name, score):
    """Add or update a student's score."""
    r.zadd(LEADERBOARD_KEY, {student_name: score})
    return JsonResponse({"message": f"{student_name} score updated to {score}"})


def get_leaderboard(request):
    """Get top 10 students with their scores."""
    top_students = r.zrevrange(
        LEADERBOARD_KEY, 0, 9, withscores=True
    )

    leaderboard = [
        {"rank": i + 1, "name": name.decode(), "score": int(score)}
        for i, (name, score) in enumerate(top_students)
    ]

    return JsonResponse({"leaderboard": leaderboard})


def get_student_rank(request, student_name):
    """Get the rank of a specific student."""
    rank = r.zrevrank(LEADERBOARD_KEY, student_name)
    score = r.zscore(LEADERBOARD_KEY, student_name)

    if rank is None:
        return JsonResponse({"error": "Student not found"}, status=404)

    return JsonResponse({
        "student": student_name,
        "rank": rank + 1,   # zrevrank is 0-indexed
        "score": int(score)
    })
```

**How it works:**
- `zadd` — inserts a member with a score (updates automatically if exists).
- `zrevrange` — returns members ordered highest-to-lowest score.
- `zrevrank` — returns the 0-indexed rank of a member (add 1 for human-readable rank).

---

### 4. Massive Student Registration

**Problem:** During peak enrollment (e.g., semester start), thousands of students register simultaneously. Processing each registration synchronously overwhelms the database and crashes the server.

**Solution:** Accept the request immediately, push the job to a **Redis queue**, and process it asynchronously with a **Celery worker**(here used without Celery for core understanding) running in the background.

#### `views.py` — Accept & Enqueue

```python
# views.py

@api_view(['POST'])
def register_student(request):
    stu_id = request.data.get('stu_id')
    stu_name = request.data.get('stu_name')
    
    if not stu_id or not stu_name:
        return Response({'error': 'Missing data'}, status=400)
    
    
    student_payload = json.dumps({'stu_id': stu_id, 'stu_name': stu_name})

    # 2. Push it instantly to the Redis queue
    r.lpush('student_registration_queue', student_payload)
    
    # 3. Return an immediate response to the client
    return Response({'message': 'Registration queued successfully!'}, status=202)

```

#### `worker.py` — Background Task Processing

```python

QUEUE_KEY = 'student_registration_queue'
BATCH_SIZE = 100          # how many students to bulk-insert per batch
BATCH_TIMEOUT = 20        # seconds to wait for next item before flushing partial batch

r = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)


def process_batch(batch: list[dict]):
    students = [
        Student(
            stu_id=item['stu_id'],
            stu_name=item['stu_name'][:50],
        )
        for item in batch
    ]
    Student.objects.bulk_create(students, ignore_conflicts=True)
    logger.info(f"Inserted {len(students)} students.")


def run():
    logger.info(f"Worker started. Listening on '{QUEUE_KEY}'...")
    batch = []

    while True:
        # brpop blocks for BATCH_TIMEOUT seconds waiting for a new item.
        # Returns (queue_name, value) or None on timeout.
        result = r.brpop(QUEUE_KEY, timeout=BATCH_TIMEOUT)

        if result:
            _, raw = result
            try:
                item = json.loads(raw)
                batch.append(item)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Skipping malformed message: {raw!r} — {e}")

        
        if batch and (len(batch) >= BATCH_SIZE or result is None):
            try:
                process_batch(batch)
            except Exception as e:
                logger.error(f"DB insert failed: {e}")
                # Re-queue failed items so they aren't lost
                for item in batch:
                    r.rpush(QUEUE_KEY, json.dumps(item))
                logger.info(f"Re-queued {len(batch)} items for retry.")
            finally:
                batch = []


if __name__ == '__main__':
    run()


```

#### Start the Worker

```bash

.../my_app> python worker.py

```

**How the full flow works:**

```
Client POST /register/bulk/
        ↓
  Django view (views.py)
  → Validates input
  → Calls register_student_task.delay()  ← pushes to Redis queue
  → Returns 202 immediately (server never blocks)

Redis Queue (broker)
  → Stores task payloads safely

 Worker (worker.py)
  → Picks up tasks from Redis
  → Writes student to DB
```

This pattern lets the server handle **tens of thousands of concurrent registrations** without breaking a sweat.

---

## 📂 Project Structure

```
redis_django/
├── redis_project/
│   ├── views.py          # All API views (cache, rate limit, leaderboard, registration)
│   ├── worker.py         # Celery background tasks
│   ├── models.py         # Django models (Student, etc.)
│   ├── urls.py           # URL routing
│   ├── settings.py       # Redis & Celery configuration
│   └── celery.py         # Celery app initialization
├── manage.py
├── requirements.txt
└── .gitignore
```

---


## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
