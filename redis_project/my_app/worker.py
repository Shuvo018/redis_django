import os, sys, json, django, redis, logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'redis_project.settings')
django.setup()

from my_app.models import Student

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

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